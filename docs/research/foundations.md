# Mathematical foundations


Understanding the mathematics is essential for explaining why the results look the way they do. This section covers the core formulations you must understand and present.

### 2.1 Neural Radiance Fields (NeRF)

A NeRF represents a scene as a continuous volumetric function:

$$
F_{\Theta} : (\mathbf{x}, \mathbf{d}) \rightarrow (\mathbf{c}, \sigma)
$$

where:

- $\mathbf{x} = (x, y, z)$ is a 3D spatial coordinate;
- $\mathbf{d} = (\theta, \phi)$ is a viewing direction;
- $\mathbf{c} = (r, g, b)$ is the emitted color; and
- $\sigma$ is the volume density.

The function $F_{\Theta}$ is parameterized by a multi-layer perceptron (MLP) with weights $\Theta$.

#### Volume Rendering

To render a pixel, a ray $\mathbf{r}(t) = \mathbf{o} + t\mathbf{d}$ is cast from the camera origin $\mathbf{o}$ through the pixel center. The expected color is computed via numerical integration:

$$
C(\mathbf{r}) = \int_{t_n}^{t_f} T(t) \cdot \sigma(\mathbf{r}(t)) \cdot \mathbf{c}(\mathbf{r}(t), \mathbf{d})\,dt
$$

where the transmittance

$$
T(t) = \exp\left(-\int_{t_n}^{t} \sigma(\mathbf{r}(s))\,ds\right)
$$

represents the probability that the ray reaches point $t$ without being occluded. In practice, this integral is discretized using stratified sampling:

$$
\hat{C}(\mathbf{r}) = \sum_{i=1}^{N} T_i \left(1 - \exp(-\sigma_i\delta_i)\right)\mathbf{c}_i
$$

with

$$
T_i = \exp\left(-\sum_{j=1}^{i-1}\sigma_j\delta_j\right),
\qquad
\delta_i = t_{i+1} - t_i.
$$

#### Positional Encoding

To allow the MLP to learn high-frequency details, coordinates are mapped through:

$$
\gamma(p) = \left(\sin(2^0\pi p), \cos(2^0\pi p), \ldots, \sin(2^{L-1}\pi p), \cos(2^{L-1}\pi p)\right)
$$

#### Hierarchical Sampling

NeRF uses two networks — a "coarse" network to identify relevant regions, then a "fine" network to sample densely there. This is why the original NeRF requires 1–2 days per scene on a single GPU.

### 2.2 3D Gaussian Splatting (3DGS)

3DGS abandons the implicit MLP entirely. Instead, it represents the scene as a set of explicit 3D Gaussian primitives:

$$
G(\mathbf{x}) = \exp\left(-\frac{1}{2}(\mathbf{x}-\boldsymbol{\mu})^T \boldsymbol{\Sigma}^{-1}(\mathbf{x}-\boldsymbol{\mu})\right)
$$

Each Gaussian is parameterized by:

- Mean position $\boldsymbol{\mu} \in \mathbb{R}^3$;
- Anisotropic covariance $\boldsymbol{\Sigma} \in \mathbb{R}^{3 \times 3}$, decomposed as $\boldsymbol{\Sigma} = \mathbf{R}\mathbf{S}\mathbf{S}^T\mathbf{R}^T$, where $\mathbf{R}$ is a rotation quaternion and $\mathbf{S}$ is a diagonal scaling matrix;
- Opacity $\alpha \in [0,1]$; and
- Spherical harmonic coefficients for view-dependent color.

#### Splatting (Rasterization)

Each 3D Gaussian is projected onto the 2D image plane. The 2D covariance is computed via the Jacobian of the projective transformation:

$$
\boldsymbol{\Sigma}' = \mathbf{J}\mathbf{W}\boldsymbol{\Sigma}\mathbf{W}^T\mathbf{J}^T
$$

where $\mathbf{W}$ is the viewing transformation and $\mathbf{J}$ is the Jacobian of the affine approximation of the projective transformation. The final pixel color is computed via front-to-back alpha compositing:

$$
C = \sum_{i \in \mathcal{N}} c_i\alpha_i \prod_{j=1}^{i-1}(1-\alpha_j)
$$

**Why 3DGS can render quickly:** Its explicit Gaussians are rasterized rather than
evaluating a NeRF along many ray samples. The original paper reports real-time
rendering in its own setting; FPS on this laptop remains to be measured.

### 2.3 Key Mathematical Differences to Highlight in Your Report

| Aspect | NeRF | 3D Gaussian Splatting |
|---|---|---|
| Representation | Implicit (MLP weights) | Explicit (point cloud of Gaussians) |
| Rendering | Ray marching + volume rendering | Differentiable rasterization (splatting) |
| Training speed | TBD for pinned Nerfacto/A4500 | TBD for pinned Splatfacto/A4500 |
| Rendering speed | TBD at fixed resolution/path | TBD at the same resolution/path |
| Memory | Model weights (~10–100 MB) | Millions of Gaussians (~100 MB–1 GB) |
| Extractability | Checkpoint is implicit; point cloud/mesh is a derived export | Gaussians are explicit and can be exported directly |
| View extrapolation | Must be measured on the chosen scenes | Must be measured on the chosen scenes |

