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
    ColmapMpirVersion = '3.0.0=he025d50_1002'
    FfmpegVersion = '6.1.1'
    LibglibVersion = '2.88.3=ha564072_4'
    LibintlVersion = '0.22.5=h5728263_3'

    NerfstudioRef = 'v1.1.5'
    NerfstudioCommit = '6b60855003011b2ca23c2fe3f8e2ca6314c69924'
    GsplatVersion = '1.4.0+pt21cu118'
    GsplatIndexUrl = 'https://docs.gsplat.studio/whl/pt21cu118'
    TinyCudaNnCommit = '2e757bbe781db59c4980d389d7dccbf5edc09669'
    HfHubVersion = '0.34.4'
    PosterRepository = 'nerfstudioteam/datasets'
    PosterRevision = '461701c17e83c3f4d2481db32315aa7df703d2f8'
    PosterImageCount = 100
    PosterRawFrameCount = 226

    NerfReferenceCommit = '14c55567a6d0fbd75d3fd12b0411f98160ba3237'
    MultinerfReferenceCommit = '5b4d4f64608ec8077222c52fdf814d40acc10bc1'
    InstantNgpReferenceCommit = 'abe236ee00cf90cfca6e36e65c00435d5b21f50a'
    GaussianSplattingReferenceCommit = '54c035f7834b564019656c3e3fcc3646292f727d'
    GsplatReferenceCommit = '4d3a3b69db4de0326f983ccf7b7b255271a17b01'
    ColmapReferenceCommit = '7019dcc195c3db1946740fb6b85bdbe854741f5f'

    MipNerf360Url = 'https://storage.googleapis.com/gresearch/refraw360/360_v2.zip'
    MipNerf360ArchiveBytes = 12535427936L
    MipNerf360ArchiveSha256 = '77332bf4eba3b8ca0c7f70130849b1e394efdd60d8f20efa6f217081d08a8b2a'
    MipNerf360Scenes = @('garden', 'bonsai', 'room')
    MipNerf360ImageCounts = @{ garden = 185; bonsai = 292; room = 311 }

    TrainIterations = 30000
    TrainCheckpointInterval = 500
    DownscaleFactor = 2
    EvalInterval = 8
    GpuSampleSeconds = 10
    # Conservative project policy, not hardware manufacturer temperature ratings.
    GpuClockMinMHz = 300
    GpuClockMaxMHz = 800
    GpuClockToleranceMHz = 15
    GpuStartTemperatureC = 65
    GpuCooldownMaximumSeconds = 300
    GpuCooldownPollSeconds = 5
    GpuStopTemperatureC = 78
    GpuStopPowerWatts = 80
    GpuMaxMemoryPercent = 95
    GpuSafetyPollSeconds = 2
    GpuSafetyQueryTimeoutSeconds = 5
    GpuEmergencyGraceSeconds = 10
    VideoFrameCount = 120
    CpuWorkerThreads = 4
    CaptureMatchingMethod = 'exhaustive'
    CaptureNumDownscales = 0  # The common canonical stage makes the training downscale once.
    RandomSeed = 42
    MinimumDatasetFreeGiB = 20
    MinimumRegistrationRatio = 0.90
    RenderWarmupFrames = 3
    RenderRepeats = 3
    DemoPort = 7007
    DemoWidth = 960
    DemoHeight = 540
    DemoQueueCapacity = 1
    # Presentation-only settings: excluded from the immutable experiment digest.
    Ui = @{
        SchemaVersion = 1
        NodeVersion = '24.16.0'
        Port = 7016
        MaxPort = 7020
        DevPort = 5176
        Selection = 'topic16-full'
        CacheBytes = 2147483648
        LeaseSeconds = 45
        HeartbeatSeconds = 10
        MaxPixels = 2073600
        DecodeLimitBytes = 629145600
        MaxVertices = 3000000
        Packages = @{
            'react' = '19.3.0'
            'react-dom' = '19.3.0'
            'three' = '0.186.1'
            '@sparkjsdev/spark' = '2.3.1'
            'lucide-react' = '1.49.0'
            'mermaid' = '12.0.0'
        }
        DevPackages = @{
            'vite' = '8.3.2'
            'typescript' = '5.9.3'
            '@vitejs/plugin-react' = '6.1.1'
            '@types/react' = '19.3.0'
            '@types/react-dom' = '19.3.0'
            '@types/three' = '0.186.0'
            '@types/node' = '26.6.4'
            'vitest' = '5.0.3'
            '@playwright/test' = '1.63.0'
            '@axe-core/playwright' = '4.13.0'
            'prettier' = '3.6.2'
        }
    }
}
