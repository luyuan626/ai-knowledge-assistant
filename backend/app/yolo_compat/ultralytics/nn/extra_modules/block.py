import torch
import torch.nn as nn


class Cut(nn.Module):
    def __init__(self, in_channels, out_channels):
        super().__init__()
        self.conv_fusion = nn.Conv2d(in_channels * 4, out_channels, kernel_size=1, stride=1)
        self.batch_norm = nn.BatchNorm2d(out_channels)

    def forward(self, x):
        parts = (x[:, :, 0::2, 0::2], x[:, :, 1::2, 0::2], x[:, :, 0::2, 1::2], x[:, :, 1::2, 1::2])
        return self.batch_norm(self.conv_fusion(torch.cat(parts, dim=1)))


class DRFD(nn.Module):
    def __init__(self, in_channels, out_channels):
        super().__init__()
        self.cut_c = Cut(in_channels=in_channels, out_channels=out_channels)
        self.conv = nn.Conv2d(in_channels, out_channels, kernel_size=3, stride=1, padding=1, groups=in_channels)
        self.conv_x = nn.Conv2d(out_channels, out_channels, kernel_size=3, stride=2, padding=1, groups=out_channels)
        self.act_x = nn.GELU()
        self.batch_norm_x = nn.BatchNorm2d(out_channels)
        self.batch_norm_m = nn.BatchNorm2d(out_channels)
        self.max_m = nn.MaxPool2d(kernel_size=2, stride=2)
        self.fusion = nn.Conv2d(3 * out_channels, out_channels, kernel_size=1, stride=1)

    def forward(self, x):
        cut = self.cut_c(x)
        features = self.conv(x)
        max_features = features
        features = self.batch_norm_x(self.act_x(self.conv_x(features)))
        max_features = self.batch_norm_m(self.max_m(max_features))
        return self.fusion(torch.cat((cut, features, max_features), dim=1))
