import torch
import torch.nn as nn
import torch.nn.functional as F


def nearest_power_of_two(n):
    lower_power = 2 ** (n.bit_length() - 1)
    higher_power = 2 ** n.bit_length()
    
    if n - lower_power < higher_power - n:
        return lower_power
    else:
        return higher_power

class FDL_loss(torch.nn.Module):
    def __init__(
        self, patch_size=5, stride=1, num_proj=256, model="VGG", phase_weight=1.0, chns=None
    ):
        """
        patch_size, stride, num_proj: SWD slice parameters
        model: feature extractor, support VGG, ResNet, Inception, EffNet
        phase_weight: weight for phase branch
        """

        super(FDL_loss, self).__init__()
   
        self.phase_weight = phase_weight
        self.stride = stride
        self.chns = chns
        for i in range(len(self.chns)):
            rand = torch.randn(num_proj, self.chns[i], patch_size, patch_size)
            rand = rand / rand.view(rand.shape[0], -1).norm(dim=1).unsqueeze(
                1
            ).unsqueeze(2).unsqueeze(3)
            self.register_buffer("rand_{}".format(i), rand)
        # print all the parameters

    def forward_once(self, x, y, idx):
        """
        x, y: input image tensors with the shape of (N, C, H, W)
        """
        rand = self.__getattr__("rand_{}".format(idx))
        projx = F.conv2d(x, rand, stride=self.stride)
        projx = projx.reshape(projx.shape[0], projx.shape[1], -1)
        projy = F.conv2d(y, rand, stride=self.stride)
        projy = projy.reshape(projy.shape[0], projy.shape[1], -1)

        # sort the convolved input
        projx, _ = torch.sort(projx, dim=-1)
        projy, _ = torch.sort(projy, dim=-1)

        # compute the mean of the sorted convolved input
        s = torch.abs(projx - projy).mean([1, 2])

        return s

    def forward(self, x, y):
        score = []
        for i in range(len(x)):
            # Transform to Fourier Space
            
            near2pow = nearest_power_of_two(x[i].shape[-1])
            if x[i].shape[-1] > near2pow:
                start_idx = (x[i].shape[-1] - near2pow) // 2
                end_idx = start_idx + near2pow
                x[i] = x[i][:, :, start_idx:end_idx, start_idx:end_idx]
                y[i] = y[i][:, :, start_idx:end_idx, start_idx:end_idx]
            else:
                pad_val = x[i].shape[-1] - near2pow
                x[i] = F.pad(x[i], (0, pad_val, 0, pad_val))
                y[i] = F.pad(y[i], (0, pad_val, 0, pad_val))

            fft_x = torch.fft.fftn(x[i], dim=(-2, -1))
            fft_y = torch.fft.fftn(y[i], dim=(-2, -1))

            # get the magnitude and phase of the extracted features
            x_mag = torch.abs(fft_x)
            x_phase = torch.angle(fft_x)
            y_mag = torch.abs(fft_y)
            y_phase = torch.angle(fft_y)

            s_amplitude = self.forward_once(x_mag, y_mag, i)
            s_phase = self.forward_once(x_phase, y_phase, i)

            score.append(s_amplitude + s_phase * self.phase_weight)

        score = sum(score)  # sumup between different layers
        score = score.mean()  # mean within batch
        return score  # the bigger the score, the bigger the difference between the two images


# if __name__ == '__main__':
#     print("FDL_loss")
#     X = torch.randn((1, 3,128,128)).cuda()
#     Y = torch.randn((1, 3,128,128)).cuda() * 2
#     loss = FDL_loss().cuda()
#     c = loss(X,Y)
#     print('loss:', c)
