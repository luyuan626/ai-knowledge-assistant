import torch.nn as nn


class MSCAAttention(nn.Module):
    def __init__(self, dim):
        super().__init__()
        self.conv0 = nn.Conv2d(dim, dim, 5, padding=2, groups=dim)
        self.conv0_1 = nn.Conv2d(dim, dim, (1, 3), padding=(0, 1), groups=dim)
        self.conv0_2 = nn.Conv2d(dim, dim, (3, 1), padding=(1, 0), groups=dim)
        self.conv1_1 = nn.Conv2d(dim, dim, (1, 7), padding=(0, 3), groups=dim)
        self.conv1_2 = nn.Conv2d(dim, dim, (7, 1), padding=(3, 0), groups=dim)
        self.conv2_1 = nn.Conv2d(dim, dim, (1, 11), padding=(0, 5), groups=dim)
        self.conv2_2 = nn.Conv2d(dim, dim, (11, 1), padding=(5, 0), groups=dim)
        self.conv4 = nn.Conv2d(dim, dim, 1)
        self.conv5 = nn.Conv2d(dim, dim, 1)

    def forward(self, x):
        identity = x.clone()
        attention = self.conv0(x)
        base = self.conv5(attention)
        local = self.conv0_2(self.conv0_1(base))
        medium = self.conv1_2(self.conv1_1(base))
        wide = self.conv2_2(self.conv2_1(base))
        return self.conv4(base + local + medium + wide) * identity * attention
