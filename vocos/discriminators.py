from typing import Tuple, List

import torch
from torch import nn, Tensor
from torch.nn import Conv2d
import torch.nn.functional as F
from torch.nn.utils import weight_norm


class MultiPeriodDiscriminator(nn.Module):
    """
    Multi-Period Discriminator module adapted from https://github.com/jik876/hifi-gan.
    Additionally, it allows incorporating conditional information with a learned embeddings table.

    Args:
        periods (tuple[int]): Tuple of periods for each discriminator.
        num_embeddings (int, optional): Number of embeddings. None means non-conditional discriminator.
            Defaults to None.
    """

    def __init__(self, periods: Tuple[int] = (2, 3, 5, 7, 11), num_embeddings: int = None):
        super().__init__()
        self.discriminators = nn.ModuleList([DiscriminatorP(period=p, num_embeddings=num_embeddings) for p in periods])

    def forward(
        self, y: torch.Tensor, y_hat: torch.Tensor, bandwidth_id: torch.Tensor = None
    ) -> Tuple[List[torch.Tensor], List[torch.Tensor], List[List[torch.Tensor]], List[List[torch.Tensor]]]:
        y_d_rs = []
        y_d_gs = []
        fmap_rs = []
        fmap_gs = []
        for d in self.discriminators:
            y_d_r, fmap_r = d(x=y, cond_embedding_id=bandwidth_id)
            y_d_g, fmap_g = d(x=y_hat, cond_embedding_id=bandwidth_id)
            y_d_rs.append(y_d_r)
            fmap_rs.append(fmap_r)
            y_d_gs.append(y_d_g)
            fmap_gs.append(fmap_g)

        return y_d_rs, y_d_gs, fmap_rs, fmap_gs


class DiscriminatorP(nn.Module):
    def __init__(
        self,
        period: int,
        kernel_size: int = 5,
        stride: int = 3,
        lrelu_slope: float = 0.1,
        num_embeddings: int = None,
    ):
        super().__init__()
        self.period = period
        self.convs = nn.ModuleList([
            weight_norm(Conv2d(   1,   32, (kernel_size, 1), (stride, 1), padding=(kernel_size // 2, 0))),
            weight_norm(Conv2d(  32,  128, (kernel_size, 1), (stride, 1), padding=(kernel_size // 2, 0))),
            weight_norm(Conv2d( 128,  512, (kernel_size, 1), (stride, 1), padding=(kernel_size // 2, 0))),
            weight_norm(Conv2d( 512, 1024, (kernel_size, 1), (stride, 1), padding=(kernel_size // 2, 0))),
            weight_norm(Conv2d(1024, 1024, (kernel_size, 1), (1,      1), padding=(kernel_size // 2, 0))),
        ])
        if num_embeddings is not None:
            self.emb = torch.nn.Embedding(num_embeddings=num_embeddings, embedding_dim=1024)
            torch.nn.init.zeros_(self.emb.weight)

        self.conv_post = weight_norm(Conv2d(1024, 1, (3, 1), 1, padding=(1, 0)))
        self.lrelu_slope = lrelu_slope

    def forward(self, x: Tensor, cond_embedding_id: None | Tensor = None) -> tuple[Tensor, list[Tensor]]:
        """
        Args:
            x :: (B, T)
        """

        # Padding and Reshape :: (B, T) -> (B, 1, T) -> (B, 1, Frame, Period)
        x = x.unsqueeze(1)
        b, c, t = x.shape
        ## Tail padding
        if t % self.period != 0:
            n_pad = self.period - (t % self.period)
            x = F.pad(x, (0, n_pad), "reflect")
            t = t + n_pad
        ## Period
        x = x.view(b, c, t // self.period, self.period)

        # Conv :: (B, 1, Frame=frm, Period=prd) -> (B, Feat, Frame<frm, Period=prd)
        fmap = []
        for i, conv in enumerate(self.convs):
            x = conv(x)
            x = F.leaky_relu(x, self.lrelu_slope)
            if i > 0:
                fmap.append(x)

        if cond_embedding_id is not None:
            emb = self.emb(cond_embedding_id)
            h = (emb.view(1, -1, 1, 1) * x).sum(dim=1, keepdims=True)
        else:
            h = 0

        # :: (B, Feat, Frame<frm, Period=prd) ->  (B, 1, Frame<frm, Period=prd)
        x = self.conv_post(x)
        fmap.append(x)
        x += h

        # :: (B, 1, Frame<frm, Period=prd) -> (B, FramePeriod=<frm*prd)
        x = torch.flatten(x, 1, -1)

        return x, fmap


class MultiResolutionDiscriminator(nn.Module):
    def __init__(
        self,
        resolutions: tuple[tuple[int, int, int]] = ((1024, 256, 1024), (2048, 512, 2048), (512, 128, 512)),
        num_embeddings: None | int = None,
    ):
        """
        Multi-Resolution Discriminator module adapted from https://github.com/mindslab-ai/univnet.
        Additionally, it allows incorporating conditional information with a learned embeddings table.

        Args:
            resolutions    - triplet (nfft, hop, winLength) for each discriminator. Default: 3/4 overlaped nfft=512/1024/2048
            num_embeddings - Number of embeddings for conditional discriminator (None for unconditional Disc)
        """
        super().__init__()

        self.discriminators = nn.ModuleList([DiscriminatorR(resolution=r, num_embeddings=num_embeddings) for r in resolutions])

    def forward(self, y: Tensor, y_hat: Tensor, bandwidth_id: None | Tensor = None) -> tuple[list[Tensor], list[Tensor], list[list[Tensor]], list[list[Tensor]]]:
        """
        Args:
            y     :: (B, T)
            y_hat :: (B, T)
        """
        y_d_rs = []
        y_d_gs = []
        fmap_rs = []
        fmap_gs = []

        for d in self.discriminators:
            y_d_r, fmap_r = d(x=y,     cond_embedding_id=bandwidth_id)
            y_d_g, fmap_g = d(x=y_hat, cond_embedding_id=bandwidth_id)
            y_d_rs.append(y_d_r)
            fmap_rs.append(fmap_r)
            y_d_gs.append(y_d_g)
            fmap_gs.append(fmap_g)

        return y_d_rs, y_d_gs, fmap_rs, fmap_gs


class DiscriminatorR(nn.Module):
    def __init__(
        self,
        resolution: Tuple[int, int, int],
        channels:       int        = 64,
        num_embeddings: None | int = None,
        lrelu_slope:    float      = 0.1,
    ):
        """
        Args:
            resolution - n_fft/hop_length/win_length
        """
        super().__init__()
        self.resolution = resolution
        self.lrelu_slope = lrelu_slope

        self.convs = nn.ModuleList([
            weight_norm(nn.Conv2d(       1,    channels, kernel_size=(7, 5), stride=(2, 2), padding=(3, 2))),
            weight_norm(nn.Conv2d(channels,    channels, kernel_size=(5, 3), stride=(2, 1), padding=(2, 1))),
            weight_norm(nn.Conv2d(channels,    channels, kernel_size=(5, 3), stride=(2, 2), padding=(2, 1))),
            weight_norm(nn.Conv2d(channels,    channels, kernel_size=3,      stride=(2, 1), padding=1)),
            weight_norm(nn.Conv2d(channels,    channels, kernel_size=3,      stride=(2, 2), padding=1)),
        ])
        if num_embeddings is not None:
            self.emb = torch.nn.Embedding(num_embeddings=num_embeddings, embedding_dim=channels)
            torch.nn.init.zeros_(self.emb.weight)
        self.conv_post = weight_norm(nn.Conv2d(channels, 1, (3, 3), padding=(1, 1)))

    def forward(self, x: Tensor, cond_embedding_id: Tensor = None) -> tuple[Tensor, list[Tensor]]:
        """wave -> (STFT) -> spec -> (Nx[conv2d-LReLU]) -> feat -> (conv2d) -> (cond) -> o_disc.
        
        Args:
            x :: (B, T)
        Returns:
              :: (B, FreqFrame)
        """
        fmap = []

        # wave2spec :: (B, T) -> (B, Freq, Frame) -> (B, 1, Freq, Frame)
        x = self.spectrogram(x).unsqueeze(1)

        # conv :: (B, 1, Freq=freq, Frame=frm) -> (B, Feat, Freq<freq, Frame<frm)
        for conv2d in self.convs:
            x = conv2d(x)
            x = F.leaky_relu(x, self.lrelu_slope)
            fmap.append(x)

        if cond_embedding_id is not None:
            emb = self.emb(cond_embedding_id)
            h = (emb.view(1, -1, 1, 1) * x).sum(dim=1, keepdims=True)
        else:
            h = 0

        # :: (B, Feat, Freq<freq, Frame<frm) -> (B, 1, Freq<freq, Frame<frm)
        x = self.conv_post(x)
        fmap.append(x)

        x += h

        # :: (B, 1, Freq<freq, Frame<frm) -> (B, FreqFrame=<freq*<frm)
        x = torch.flatten(x, 1, -1)

        return x, fmap

    def spectrogram(self, x: Tensor) -> Tensor:
        """
        Args:
            x :: (B, T)
        Returns:
              :: (B, Freq, Frame)
        """
        n_fft, hop_length, win_length = self.resolution

        # NOTE: interestingly rectangular window kind of works here
        mag_spec = torch.stft(x, n_fft=n_fft, hop_length=hop_length, win_length=win_length, window=None, center=True, return_complex=True).abs()

        return mag_spec
