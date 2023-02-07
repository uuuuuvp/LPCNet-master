import numpy as np
import torch
from torch import nn
import torch.nn.functional as F

def new_specgram(N, device):
    x = np.arange(N, dtype='float32')
    w = np.sin(.5*np.pi*np.sin((x+.5)/N*np.pi)**2)
    w = torch.tensor(x).to(device)
    def compute_specgram(x):
        X = torch.stft(x, N, hop_length=N//2, return_complex=True, center=False, window=w)
        return 20*torch.log10(1e-5+torch.abs(X))

    return compute_specgram

def sig_l1(y_true, y_pred):
    return torch.mean(abs(y_true-y_pred))

def spec_l1(spec, y_true, y_pred):
    return torch.mean(abs(spec(y_true)-spec(y_pred)))

# weight initialization and clipping
def init_weights(module):
    if isinstance(module, nn.GRU):
        for p in module.named_parameters():
            if p[0].startswith('weight_hh_'):
                nn.init.orthogonal_(p[1])

class CELPNetCond(nn.Module):
    def __init__(self, feature_dim=20, cond_size=256):
        super(CELPNetCond, self).__init__()

        self.feature_dim = feature_dim
        self.cond_size = cond_size

        self.fdense1 = nn.Linear(self.feature_dim, self.cond_size)
        self.fconv1 = nn.Conv1d(self.cond_size, self.cond_size, kernel_size=3, padding='valid')
        self.fconv2 = nn.Conv1d(self.cond_size, self.cond_size, kernel_size=3, padding='valid')
        self.fdense2 = nn.Linear(self.cond_size, self.cond_size)

        self.apply(init_weights)

    def forward(self, features):
        tmp = torch.tanh(self.fdense1(features))
        tmp = tmp.permute(0, 2, 1)
        tmp = torch.tanh(self.fconv1(tmp))
        tmp = torch.tanh(self.fconv2(tmp))
        tmp = tmp.permute(0, 2, 1)
        tmp = torch.tanh(self.fdense2(tmp))
        return tmp

class CELPNetSub(nn.Module):
    def __init__(self, subframe_size=40, nb_subframes=4, cond_size=256):
        super(CELPNetSub, self).__init__()

        self.subframe_size = subframe_size
        self.nb_subframes = nb_subframes
        self.cond_size = cond_size

        self.sig_dense1 = nn.Linear(self.subframe_size+self.cond_size, self.cond_size)
        self.sig_dense2 = nn.Linear(self.cond_size, self.cond_size)
        self.gru1 = nn.GRUCell(self.cond_size, self.cond_size)
        self.gru2 = nn.GRUCell(self.cond_size, self.cond_size)
        self.gru3 = nn.GRUCell(self.cond_size, self.cond_size)
        self.sig_dense_out = nn.Linear(self.cond_size, self.subframe_size)

        self.apply(init_weights)

    def forward(self, cond, prev, states):
        tmp = torch.cat((cond, prev), 1)
        tmp = torch.tanh(self.sig_dense1(tmp))
        tmp = torch.tanh(self.sig_dense2(tmp))
        gru1_state = self.gru1(tmp, states[0])
        gru2_state = self.gru2(gru1_state, states[1])
        gru3_state = self.gru3(gru2_state, states[2])
        return torch.tanh(self.sig_dense_out(gru3_state)), (gru1_state, gru2_state, gru3_state)

class CELPNet(nn.Module):
    def __init__(self, subframe_size=40, nb_subframes=4, feature_dim=20, cond_size=256, stateful=False):
        super(CELPNet, self).__init__()

        self.subframe_size = subframe_size
        self.nb_subframes = nb_subframes
        self.frame_size = self.subframe_size*self.nb_subframes
        self.feature_dim = feature_dim
        self.cond_size = cond_size
        self.stateful = stateful

        self.cond_net = CELPNetCond(feature_dim=feature_dim, cond_size=cond_size)
        self.sig_net = CELPNetSub(subframe_size=subframe_size, nb_subframes=nb_subframes, cond_size=cond_size)

    def forward(self, features, pre, nb_frames):
        device = features.device
        batch_size = features.size(0)

        states = (
            torch.zeros(batch_size, self.cond_size).to(device),
            torch.zeros(batch_size, self.cond_size).to(device),
            torch.zeros(batch_size, self.cond_size).to(device)
        )

        sig = torch.zeros((batch_size, 0)).to(device)
        cond = self.cond_net(features)
        if pre is None:
            nb_pre_frames = 0
            prev = torch.zeros(batch_size, self.subframe_size).to(device)
        else:
            nb_pre_frames = pre.size(1)//self.frame_size
            for n in range(nb_pre_frames):
                for k in range(self.nb_subframes):
                    pos = n*self.frame_size + k*self.subframe_size
                    if pos > 0:
                        _, states = self.sig_net(cond[:, n, :], pre[:, pos-self.subframe_size:pos], states)
            prev = pre[:, -self.subframe_size:]
        for n in range(nb_frames):
            for k in range(self.nb_subframes):
                pos = n*self.frame_size + k*self.subframe_size
                out, states = self.sig_net(cond[:, nb_pre_frames+n, :], prev, states)
                sig = torch.cat([sig, out], 1)
                prev = out
        return sig
