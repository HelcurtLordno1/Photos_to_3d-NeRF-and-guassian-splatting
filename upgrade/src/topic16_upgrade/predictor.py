"""Fixed ridge forecast with leave-one-scene-out preprocessing and abstention."""
import numpy as np
from .contracts import digest_json
from .capture import FEATURE_SCHEMA

FIELDS = ('views', 'sharpness', 'clipped_fraction', 'coverage_bins', 'radius_spread')


def fit(x, y, alpha):
    mean, scale = x.mean(axis=0), x.std(axis=0)
    scale[scale < 1e-8] = 1
    z = np.column_stack([np.ones(len(x)), (x - mean) / scale])
    penalty = np.eye(z.shape[1]) * alpha; penalty[0, 0] = 0
    weights = np.linalg.solve(z.T @ z + penalty, z.T @ y)
    return mean, scale, weights


def apply(model, x):
    mean, scale, weights = model
    return np.column_stack([np.ones(len(x)), (x - mean) / scale]) @ weights


def train(rows, method, budget, evaluator_id, minimum_groups=4, alpha=10.):
    samples = [r for r in rows if r['method'] == method and r['budget'] == budget
               and r['evaluator_id'] == evaluator_id and r.get('feature_schema') == FEATURE_SCHEMA]
    groups = sorted({r['scene_group'] for r in samples})
    base = {'schema_version': 'capture-predictor-1', 'feature_schema': FEATURE_SCHEMA,
            'kind': 'capture-only', 'method': method, 'budget': budget, 'evaluator_id': evaluator_id,
            'training_groups': groups, 'samples': len(samples), 'alpha': alpha, 'fields': list(FIELDS)}
    if len(groups) < minimum_groups:
        return {**base, 'status': 'insufficient-evidence', 'reason': f'Requires {minimum_groups} independent scene groups; found {len(groups)}'}
    x = np.asarray([[r['features'][f] for f in FIELDS] for r in samples], dtype=float)
    y = np.asarray([r['metrics']['psnr'] for r in samples], dtype=float)
    if not np.isfinite(x).all() or not np.isfinite(y).all():
        raise ValueError('Predictor samples must be finite')
    results = []
    for group in groups:
        test = np.asarray([r['scene_group'] == group for r in samples]); training = ~test
        learned = apply(fit(x[training], y[training], alpha), x[test])
        views = apply(fit(x[training, :1], y[training], alpha), x[test, :1])
        for i, a, b in zip(np.where(test)[0], learned, views):
            results.append({'scene_group': group, 'run_key': samples[i]['run_key'], 'observed': float(y[i]),
                            'predicted': float(a), 'mean_baseline': float(y[training].mean()), 'views_baseline': float(b),
                            'training_groups': [g for g in groups if g != group]})
    validation = {}
    for field in ('predicted', 'mean_baseline', 'views_baseline'):
        error = np.asarray([r[field] - r['observed'] for r in results])
        validation[field] = {'mae_db': float(np.abs(error).mean()), 'rmse_db': float(np.sqrt(np.mean(error**2)))}
    mean, scale, weights = fit(x, y, alpha)
    validated = validation['predicted']['mae_db'] < min(validation[k]['mae_db'] for k in ('mean_baseline', 'views_baseline'))
    model = {**base, 'status': 'exploratory-validated' if validated else 'insufficient-evidence',
             'reason': 'LOSO exploratory; few independent scenes' if validated else 'Capture model did not beat both simple predictors',
             'validation': validation, 'out_of_fold': results, 'mean': mean.tolist(), 'scale': scale.tolist(),
             'weights': weights.tolist(), 'minimum': x.min(axis=0).tolist(), 'maximum': x.max(axis=0).tolist(),
             'labels_hash': digest_json(samples)}
    model['model_id'] = digest_json(model)
    return model


def predict(model, features, method, budget, evaluator_id):
    refusal = {'status': 'insufficient-evidence', 'model_id': model.get('model_id'), 'prediction': None}
    if model['status'] != 'exploratory-validated':
        return {**refusal, 'reason': model['reason']}
    if (method, budget, evaluator_id) != (model['method'], model['budget'], model['evaluator_id']):
        return {**refusal, 'reason': 'Method, total schedule or evaluator outside validated scope'}
    x = np.asarray([features[f] for f in FIELDS], dtype=float)
    if not np.isfinite(x).all() or np.any(x < model['minimum']) or np.any(x > model['maximum']):
        return {**refusal, 'reason': 'Capture features outside observed training range'}
    value = float(apply((np.asarray(model['mean']), np.asarray(model['scale']), np.asarray(model['weights'])), x[None])[0])
    return {'status': 'exploratory', 'psnr_db': value, 'model_id': model['model_id'],
            'training_groups': model['training_groups'], 'target_budget': budget,
            'feature_schema': model['feature_schema'], 'validation': model['validation'],
            'interval': None, 'reason': 'No calibrated prediction interval'}
