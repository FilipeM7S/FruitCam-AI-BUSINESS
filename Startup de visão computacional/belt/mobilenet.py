from functools import partial

from torch import nn

BLOCKS = (
    (16, 3, 16, 16, True, False, 2),
    (16, 3, 72, 24, False, False, 2),
    (24, 3, 88, 24, False, False, 1),
    (24, 5, 96, 40, True, True, 2),
    (40, 5, 240, 40, True, True, 1),
    (40, 5, 240, 40, True, True, 1),
    (40, 5, 120, 48, True, True, 1),
    (48, 5, 144, 48, True, True, 1),
    (48, 5, 288, 96, True, True, 2),
    (96, 5, 576, 96, True, True, 1),
    (96, 5, 576, 96, True, True, 1),
)
LAST_CONV = 576
LAST_CHANNEL = 1024
Norm = partial(nn.BatchNorm2d, eps=0.001, momentum=0.01)


def divisible(v, divisor=8):
    new = max(divisor, int(v + divisor / 2) // divisor * divisor)
    return new + divisor if new < 0.9 * v else new


def conv_norm(inp, out, kernel, stride=1, groups=1, activation=None):
    layers = [nn.Conv2d(inp, out, kernel, stride, (kernel - 1) // 2, groups=groups, bias=False), Norm(out)]
    if activation is not None:
        layers.append(activation(inplace=True))
    return nn.Sequential(*layers)


class SqueezeExcitation(nn.Module):
    def __init__(self, channels, squeeze):
        super().__init__()
        self.avgpool = nn.AdaptiveAvgPool2d(1)
        self.fc1 = nn.Conv2d(channels, squeeze, 1)
        self.fc2 = nn.Conv2d(squeeze, channels, 1)
        self.activation = nn.ReLU()
        self.scale_activation = nn.Hardsigmoid()

    def forward(self, x):
        return self.scale_activation(self.fc2(self.activation(self.fc1(self.avgpool(x))))) * x


class InvertedResidual(nn.Module):
    def __init__(self, inp, kernel, expanded, out, use_se, use_hs, stride):
        super().__init__()
        self.residual = stride == 1 and inp == out
        activation = nn.Hardswish if use_hs else nn.ReLU
        layers = []
        if expanded != inp:
            layers.append(conv_norm(inp, expanded, 1, activation=activation))
        layers.append(conv_norm(expanded, expanded, kernel, stride, expanded, activation))
        if use_se:
            layers.append(SqueezeExcitation(expanded, divisible(expanded // 4)))
        layers.append(conv_norm(expanded, out, 1))
        self.block = nn.Sequential(*layers)

    def forward(self, x):
        return x + self.block(x) if self.residual else self.block(x)


class MobileNetV3Small(nn.Module):
    def __init__(self, num_classes):
        super().__init__()
        layers = [conv_norm(3, 16, 3, 2, activation=nn.Hardswish)]
        layers += [InvertedResidual(*cfg) for cfg in BLOCKS]
        layers.append(conv_norm(BLOCKS[-1][3], LAST_CONV, 1, activation=nn.Hardswish))
        self.features = nn.Sequential(*layers)
        self.avgpool = nn.AdaptiveAvgPool2d(1)
        self.classifier = nn.Sequential(nn.Linear(LAST_CONV, LAST_CHANNEL), nn.Hardswish(inplace=True), nn.Dropout(p=0.2, inplace=True), nn.Linear(LAST_CHANNEL, num_classes))

    def forward(self, x):
        return self.classifier(self.avgpool(self.features(x)).flatten(1))
