@{
    SchemaVersion = 'quality-confirmation-1'
    Study = 'tea-quality-v5'
    ReferenceStudy = 'tea-research-v4'
    Seeds = @(17,2026)
    MaximumGpuSeconds = 10800
    MinimumFreeGiB = 40
    MeanParityTargetDb = 35
    MinimumViewParityDb = 30
    MaximumBrowserP95Ms = 33.3
    MaximumPsnrLossVsQ1 = 0.2
    MaximumLpipsRatioVsQ1 = 1.05
    MinimumSeedMeanPsnrGain = 0.5
    MaximumMeanTrainingRatio = 0.9
    RequiredFavourableSeeds = 2
    OrbitFrames = 120
    BrowserWarmupFrames = 30
    BrowserMeasuredFrames = 180
}
