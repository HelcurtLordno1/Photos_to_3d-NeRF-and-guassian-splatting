@{
    Study = 'tea-research-v3'
    Scene = 'custom:tea_sets_2'
    ImprovedGsCommit = '20b5db343a87c2f9fb4b70c6e39ff1f042a8a47a'
    EnvironmentName = 'topic16-improvedgs-v1'
    CloneFrom = 'topic16-upgrade-ns115'
    TorchVersion = '2.1.2+cu118'
    CudaToolkitVersion = '11.8'
    # Explicit tested compatibility recipe, not the authors' cu121 recipe.
    Iterations = 30000
    Seed = 42
    GaussianBudget = 300000
    AbsoluteGaussianSafetyLimit = 1500000
    MaximumTrainingSecondsPerMethod = 10800
    MaximumTotalTrainingSeconds = 21600
    CheckpointInterval = 500
    TrainMemoryTargetMiB = 12288
    Methods = @('absgs','improvedgs')
    SupersampleFactor = 2
    Filter = 'torch-area-float-rgb-v1'
}
