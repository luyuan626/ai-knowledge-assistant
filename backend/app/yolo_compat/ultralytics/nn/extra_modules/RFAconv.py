import torch
import torch.nn as nn
from einops import rearrange

from ultralytics.nn.modules.conv import Conv


class SE(nn.Module):
    def __init__(self, in_channel, ratio=16):
        super().__init__()
        self.gap = nn.AdaptiveAvgPool2d((1, 1))
        self.fc = nn.Sequential(
            nn.Linear(in_channel, ratio, bias=False),
            nn.ReLU(),
            nn.Linear(ratio, in_channel, bias=False),
            nn.Sigmoid(),
        )

    def forward(self, x):
        batch, channels = x.shape[:2]
        return self.fc(self.gap(x).view(batch, channels)).view(batch, channels, 1, 1)


class RFCBAMConv(nn.Module):
    def __init__(self, in_channel, out_channel, kernel_size=3, stride=1):
        super().__init__()
        if kernel_size % 2 == 0:
            raise ValueError("kernel_size must be odd")
        self.kernel_size = kernel_size
        self.generate = nn.Sequential(
            nn.Conv2d(in_channel, in_channel * kernel_size**2, kernel_size, padding=kernel_size // 2, stride=stride, groups=in_channel, bias=False),
            nn.BatchNorm2d(in_channel * kernel_size**2),
            nn.ReLU(),
        )
        self.get_weight = nn.Sequential(nn.Conv2d(2, 1, kernel_size=3, padding=1, bias=False), nn.Sigmoid())
        self.se = SE(in_channel)
        self.conv = Conv(in_channel, out_channel, k=kernel_size, s=kernel_size, p=0)

    def forward(self, x):
        batch, channels = x.shape[:2]
        features = self.generate(x)
        height, width = features.shape[2:]
        features = features.view(batch, channels, self.kernel_size**2, height, width)
        features = rearrange(features, "b c (n1 n2) h w -> b c (h n1) (w n2)", n1=self.kernel_size, n2=self.kernel_size)
        channel_features = features * self.se(x)
        spatial_features = torch.cat((features.max(dim=1, keepdim=True).values, features.mean(dim=1, keepdim=True)), dim=1)
        return self.conv(channel_features * self.get_weight(spatial_features))
