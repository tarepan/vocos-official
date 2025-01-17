
charactr/vocos-mel-24khz/config.yaml @ 2023-08-09

```toml
feature_extractor:
  class_path: vocos.feature_extractors.MelSpectrogramFeatures
  init_args:
    sample_rate: 24000
    n_fft:        1024 # 42.66 msec
    hop_length:    256 # 10.66 msec, 3/4 overlap
    n_mels:        100
    padding:    center

backbone:
  class_path: vocos.models.VocosBackbone
  init_args:
    input_channels: 100
    dim: 512
    intermediate_dim: 1536
    num_layers: 8

head:
  class_path: vocos.heads.ISTFTHead
  init_args:
    dim: 512
    n_fft: 1024
    hop_length: 256
    padding: center
```
