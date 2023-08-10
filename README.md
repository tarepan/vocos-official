<div align="center">

# Vocos <!-- omit in toc -->
[![ColabBadge]][notebook]
[![PaperBadge]][paper]  

</div>

Clone of official ***Vocos***, Frame-level vocoder based on Fourier-basis.

<!-- Auto-generated by "Markdown All in One" extension -->
- [Demo](#demo)
- [Usage](#usage)
  - [Install](#install)
  - [Train](#train)
  - [Inference](#inference)
- [Results](#results)
- [References](#references)


## Demo
[official demo][demo page]

## Usage
### Install
```bash
# pip install "torch==2.0.0" -q      # Based on your environment (validated with vX.YZ)
# pip install "torchaudio==2.0.1" -q # Based on your environment
pip install git+https://github.com/tarepan/vocos-official
```

### Inference
#### mel-to-wave Resynthesis
```python
import torchaudio
from vocos import Vocos

vocos = Vocos.from_pretrained("charactr/vocos-mel-24khz")

y, sr = torchaudio.load(YOUR_AUDIO_FILE)
if y.size(0) > 1:  # mix to mono
    y = y.mean(dim=0, keepdim=True)
y = torchaudio.functional.resample(y, orig_freq=sr, new_freq=24000)
y_hat = vocos(y)
```

#### Reconstruct audio from EnCodec tokens

Additionally, you need to provide a `bandwidth_id` which corresponds to the embedding for bandwidth from the
list: `[1.5, 3.0, 6.0, 12.0]`.

```python
vocos = Vocos.from_pretrained("charactr/vocos-encodec-24khz")

audio_tokens = torch.randint(low=0, high=1024, size=(8, 200))  # 8 codeboooks, 200 frames
features = vocos.codes_to_features(audio_tokens)
bandwidth_id = torch.tensor([2])  # 6 kbps

audio = vocos.decode(features, bandwidth_id=bandwidth_id)
```

Copy-synthesis from a file: It extracts and quantizes features with EnCodec, then reconstructs them with Vocos in a
single forward pass.

```python
y, sr = torchaudio.load(YOUR_AUDIO_FILE)
if y.size(0) > 1:  # mix to mono
    y = y.mean(dim=0, keepdim=True)
y = torchaudio.functional.resample(y, orig_freq=sr, new_freq=24000)

y_hat = vocos(y, bandwidth_id=bandwidth_id)
```

#### Integrate with 🐶 [Bark](https://github.com/suno-ai/bark) text-to-audio model

See [example notebook](notebooks%2FBark%2BVocos.ipynb).

#### Pre-trained models
Improved versions (2500K steps)

| Model Name                                                                          | Dataset       | Training Iterations | Parameters |
|-------------------------------------------------------------------------------------|---------------|---------------------|------------|
| [charactr/vocos-mel-24khz](https://huggingface.co/charactr/vocos-mel-24khz)         | LibriTTS      | 2.5 M               | 13.5 M     |
| [charactr/vocos-encodec-24khz](https://huggingface.co/charactr/vocos-encodec-24khz) | DNS Challenge | 2.5 M               |  7.9 M     |

### Train
Jump to ☞ [![ColabBadge]][notebook], then Run. That's all!

## References
### Original paper <!-- omit in toc -->
[![PaperBadge]][paper]  
<!-- Generated with the tool -> https://arxiv2bibtex.org/?q=2306.00814&format=bibtex -->
```bibtex
@misc{2306.00814,
Author = {Hubert Siuzdak},
Title = {Vocos: Closing the gap between time-domain and Fourier-based neural vocoders for high-quality audio synthesis},
Year = {2023},
Eprint = {arXiv:2306.00814},
}
```

### Acknowlegements <!-- omit in toc -->
- [Official Vocos](https://github.com/charactr-platform/vocos)


[ColabBadge]:https://colab.research.google.com/assets/colab-badge.svg

[paper]:https://arxiv.org/abs/2306.00814
[PaperBadge]:https://img.shields.io/badge/paper-arxiv.2306.00814-B31B1B.svg
[notebook]:https://colab.research.google.com/github/tarepan/vocos-official/blob/main/vocos.ipynb
[demo page]:https://charactr-platform.github.io/vocos/