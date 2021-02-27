from typing import Tuple
from torch import Tensor
import torch
import torch.nn as nn

from utils.attention import xattn_score_t2i, xattn_score_i2t

DEVICE = "cuda"


class ContrastiveLoss(nn.Module):
    """
    Compute contrastive loss
    """

    def __init__(
        self,
        cross_attn: str,
        raw_feature_norm: str,
        agg_func: str,
        margin: float,
        lambda_lse: float,
        lambda_softmax: float,
        max_violation: bool=False,
    ):
        super(ContrastiveLoss, self).__init__()
        self.cross_attn = cross_attn
        self.raw_feature_norm = raw_feature_norm
        self.agg_func = agg_func
        self.margin = margin
        self.lambda_lse = lambda_lse
        self.lambda_softmax = lambda_softmax
        self.max_violation = max_violation

    def forward(self, im: Tensor, s: Tensor, s_l: int) -> float:
        params = {
            "lambda_softmax": self.lambda_softmax,
            "lambda_lse": self.lambda_lse,
            "agg_func": self.agg_func,
            "raw_feature_norm": self.raw_feature_norm,
        }
        # compute image-sentence score matrix
        if self.cross_attn == "t2i":
            scores = xattn_score_t2i(im, s, s_l, params)
        elif self.cross_attn == "i2t":
            scores = xattn_score_i2t(im, s, s_l, params)
        else:
            raise ValueError("unknown first norm type:", self.raw_feature_norm)
        diagonal = scores.diag().view(im.size(0), 1)
        d1 = diagonal.expand_as(scores)
        d2 = diagonal.t().expand_as(scores)

        # compare every diagonal score to scores in its column
        # caption retrieval
        cost_s = (self.margin + scores - d1).clamp(min=0)
        # compare every diagonal score to scores in its row
        # image retrieval
        cost_im = (self.margin + scores - d2).clamp(min=0)

        # clear diagonals
        mask = torch.eye(scores.size(0)) > 0.5
        I = mask.to(DEVICE)
        cost_s = cost_s.masked_fill_(I, 0)
        cost_im = cost_im.masked_fill_(I, 0)

        # keep the maximum violating negative for each query
        if self.max_violation:
            cost_s = cost_s.max(1)[0]
            cost_im = cost_im.max(0)[0]

        return cost_s.sum() + cost_im.sum()
        