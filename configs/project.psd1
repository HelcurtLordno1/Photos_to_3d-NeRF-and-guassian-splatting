@{
    # Reproducible native-Windows runtime. Keep all executable pins here.
    EnvironmentName = 'topic16-ns115'
    PythonVersion = '3.10'
    TorchVersion = '2.1.2+cu118'
    TorchvisionVersion = '0.16.2+cu118'
    TorchIndexUrl = 'https://download.pytorch.org/whl/cu118'
    CudaToolkitChannel = 'nvidia/label/cuda-11.8.0'
    CudaToolkitVersion = '11.8.0'
    ColmapVersion = '3.9.1'

    NerfstudioRef = 'v1.1.5'
    NerfstudioCommit = '6b60855003011b2ca23c2fe3f8e2ca6314c69924'
    GsplatVersion = '1.4.0+pt21cu118'
    GsplatIndexUrl = 'https://docs.gsplat.studio/whl/pt21cu118'
    TinyCudaNnCommit = '2e757bbe781db59c4980d389d7dccbf5edc09669'
    HfHubVersion = '0.34.4'
    PosterRepository = 'nerfstudioteam/datasets'
    PosterRevision = '461701c17e83c3f4d2481db32315aa7df703d2f8'

    NerfReferenceCommit = '14c55567a6d0fbd75d3fd12b0411f98160ba3237'
    MultinerfReferenceCommit = '5b4d4f64608ec8077222c52fdf814d40acc10bc1'
    InstantNgpReferenceCommit = 'abe236ee00cf90cfca6e36e65c00435d5b21f50a'
    GaussianSplattingReferenceCommit = '54c035f7834b564019656c3e3fcc3646292f727d'
    GsplatReferenceCommit = '4d3a3b69db4de0326f983ccf7b7b255271a17b01'
    ColmapReferenceCommit = '7019dcc195c3db1946740fb6b85bdbe854741f5f'

    MipNerf360Url = 'https://storage.googleapis.com/gresearch/refraw360/360_v2.zip'
    MipNerf360ArchiveBytes = 12535427936L
    MipNerf360Scenes = @('garden', 'bonsai', 'room')

    TrainIterations = 30000
    DownscaleFactor = 2
    EvalInterval = 8
    GpuSampleSeconds = 10
    RandomSeed = 42
    MinimumDatasetFreeGiB = 20
}
