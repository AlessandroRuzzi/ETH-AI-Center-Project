import numpy as np
import torch
from utils import *


class MuRP(torch.nn.Module):
    def __init__(self, d, dim, entity_mat=None):
        super(MuRP, self).__init__()
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        self.Eh = torch.nn.Embedding(len(d.entities), dim, padding_idx=0)
        if entity_mat is not None:
            entity_mat = entity_mat.double()
            self.Eh.weight.data = self.Eh.weight.data.double()
            self.Eh.weight.data = 1e-3 * entity_mat
            self.Eh.to(device)
        else:
            self.Eh.weight.data = 1e-3 * torch.randn(
                (len(d.entities), dim), dtype=torch.double, device=device
            )

        self.rvh = torch.nn.Embedding(len(d.relations), dim, padding_idx=0)
        self.rvh.weight.data = 1e-3 * torch.randn(
            (len(d.relations), dim), dtype=torch.double, device=device
        )
        self.Wu = torch.nn.Parameter(
            torch.tensor(
                np.random.uniform(-1, 1, (len(d.relations), dim)),
                dtype=torch.double,
                requires_grad=True,
                device=device,
            )
        )
        self.bs = torch.nn.Parameter(
            torch.zeros(
                len(d.entities), dtype=torch.double, requires_grad=True, device=device
            )
        )
        self.bo = torch.nn.Parameter(
            torch.zeros(
                len(d.entities), dtype=torch.double, requires_grad=True, device=device
            )
        )
        self.loss = torch.nn.BCEWithLogitsLoss()

    def forward(self, u_idx, r_idx, v_idx):
        u = self.Eh.weight[u_idx]
        v = self.Eh.weight[v_idx]
        Ru = self.Wu[r_idx]
        rvh = self.rvh.weight[r_idx]

        u = torch.where(
            torch.norm(u, 2, dim=-1, keepdim=True) >= 1,
            u / (torch.norm(u, 2, dim=-1, keepdim=True) - 1e-5),
            u,
        )
        v = torch.where(
            torch.norm(v, 2, dim=-1, keepdim=True) >= 1,
            v / (torch.norm(v, 2, dim=-1, keepdim=True) - 1e-5),
            v,
        )
        rvh = torch.where(
            torch.norm(rvh, 2, dim=-1, keepdim=True) >= 1,
            rvh / (torch.norm(rvh, 2, dim=-1, keepdim=True) - 1e-5),
            rvh,
        )
        u_e = p_log_map(u)
        u_W = u_e * Ru
        u_m = p_exp_map(u_W)
        v_m = p_sum(v, rvh)
        u_m = torch.where(
            torch.norm(u_m, 2, dim=-1, keepdim=True) >= 1,
            u_m / (torch.norm(u_m, 2, dim=-1, keepdim=True) - 1e-5),
            u_m,
        )
        v_m = torch.where(
            torch.norm(v_m, 2, dim=-1, keepdim=True) >= 1,
            v_m / (torch.norm(v_m, 2, dim=-1, keepdim=True) - 1e-5),
            v_m,
        )

        sqdist = (
            2.0
            * artanh(
                torch.clamp(torch.norm(p_sum(-u_m, v_m), 2, dim=-1), 1e-10, 1 - 1e-5)
            )
        ) ** 2

        return -sqdist + self.bs[u_idx] + self.bo[v_idx]


class MuRE(torch.nn.Module):
    def __init__(
        self, d, dim, entity_mat=None, rel_vec=None, rel_mat=None, mult_factor=1e-3
    ):
        super(MuRE, self).__init__()
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        self.E = torch.nn.Embedding(len(d.entities), dim, padding_idx=0)
        if entity_mat is not None:
            entity_mat = entity_mat.double()
            self.E.weight.data = self.E.weight.data.double()
            self.E.weight.data = mult_factor * entity_mat
            self.E.to(device)
        else:
            self.E.weight.data = self.E.weight.data.double()
            self.E.weight.data = mult_factor * torch.randn(
                (len(d.entities), dim), dtype=torch.double, device=device
            )

        if rel_mat is not None:
            self.Wu = torch.nn.Parameter(rel_mat.repeat(2, 1))
            self.Wu.requires_grad = True
            self.Wu.to(device)
        else:
            self.Wu = torch.nn.Parameter(
                torch.tensor(
                    np.random.uniform(-1, 1, (len(d.relations), dim)),
                    dtype=torch.double,
                    requires_grad=True,
                    device=device,
                )
            )

        self.rv = torch.nn.Embedding(len(d.relations), dim, padding_idx=0)
        if rel_vec is not None:
            self.rv.weight.data = rel_vec.repeat(2, 1)
            self.rv.to(device)
        else:
            self.rv.weight.data = self.rv.weight.data.double()
            self.rv.weight.data = mult_factor * torch.randn(
                (len(d.relations), dim), dtype=torch.double, device=device
            )

        self.bs = torch.nn.Parameter(
            torch.zeros(
                len(d.entities), dtype=torch.double, requires_grad=True, device=device
            )
        )
        self.bo = torch.nn.Parameter(
            torch.zeros(
                len(d.entities), dtype=torch.double, requires_grad=True, device=device
            )
        )
        self.loss = torch.nn.BCEWithLogitsLoss()

    def forward(self, u_idx, r_idx, v_idx):
        u = self.E.weight[u_idx]
        v = self.E.weight[v_idx]
        Ru = self.Wu[r_idx]
        rv = self.rv.weight[r_idx]

        u_W = u * Ru

        sqdist = torch.sum(torch.pow(u_W - (v + rv), 2), dim=-1)
        return -sqdist + self.bs[u_idx] + self.bo[v_idx]


class MuRE_TransE(torch.nn.Module):
    def __init__(
        self,
        d,
        dim,
        entity_mat=None,
        rel_vec=None,
        rel_mat=None,
        transe_loss=False,
        mult_factor=1e-3,
        transe_enable_bias=False,
        transe_bias_mode=None,
        transe_bias_init=None, 
        transe_enable_mtx=False,
        transe_enable_vec=False,
        distmult_score_function=False,
        distmult_sqdist=False,
        distmult_sqdist_mode=None,
    ):
        super(MuRE_TransE, self).__init__()
        print("Initializing Mure_TransE model...")

        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        self.transe_enable_bias = transe_enable_bias
        self.transe_bias_mode = transe_bias_mode
        self.transe_bias_init = transe_bias_init
        self.transe_enable_mtx = transe_enable_mtx
        self.transe_enable_vec = transe_enable_vec
        self.distmult_score_function = distmult_score_function
        self.distmult_sqdist = distmult_sqdist
        self.distmult_sqdist_mode = distmult_sqdist_mode

        self.E = torch.nn.Embedding(len(d.entities), dim, padding_idx=0)
        if entity_mat is not None:
            self.E.weight.data = self.E.weight.data.double()
            self.E.weight.data = mult_factor * entity_mat.double()
            self.E.to(device)
        else:
            self.E.weight.data = self.E.weight.data.double()
            self.E.weight.data = mult_factor * torch.randn(
                (len(d.entities), dim), dtype=torch.double, device=device
            )

        if rel_mat is not None:
            self.Wu = torch.nn.Parameter(rel_mat.repeat(2, 1))
            self.Wu.requires_grad = True
            self.Wu.to(device)
        else:
            self.Wu = torch.nn.Parameter(
                torch.tensor(
                    np.random.uniform(-1, 1, (len(d.relations), dim)),
                    dtype=torch.double,
                    requires_grad=True,
                    device=device,
                )
            )

        self.rv = torch.nn.Embedding(len(d.relations), dim, padding_idx=0)
        if rel_vec is not None:
            self.rv.weight.data = rel_vec.repeat(2, 1)
            self.rv.to(device)
        else:
            self.rv.weight.data = self.rv.weight.data.double()
            self.rv.weight.data = mult_factor * torch.randn(
                (len(d.relations), dim), dtype=torch.double, device=device
            )

        if transe_loss:
            self.loss = torch.nn.MarginRankingLoss(margin=5)
        else:
            self.loss = torch.nn.BCEWithLogitsLoss()

        self.bs = torch.nn.Parameter(
            torch.zeros(
                len(d.entities), dtype=torch.double, requires_grad=True, device=device
            )
        )
        
        if self.transe_bias_init == "ones":
            self.bo = torch.nn.Parameter(
                torch.ones(
                    len(d.entities), dtype=torch.double, requires_grad=True, device=device
                )
            )
        else:
            self.bo = torch.nn.Parameter(
                torch.zeros(
                    len(d.entities), dtype=torch.double, requires_grad=True, device=device
                )
            )

    def forward(self, u_idx, r_idx, v_idx):
        u = self.E.weight[u_idx]
        v = self.E.weight[v_idx]
        Ru = self.Wu[r_idx]
        rv = self.rv.weight[r_idx]

        if not self.transe_enable_vec:
            rv = torch.zeros(
                rv.shape,
                dtype=torch.double,
                device=torch.device("cuda" if torch.cuda.is_available() else "cpu"),
            )

        if self.transe_enable_mtx:
            u_W = u * Ru
            sqdist = torch.sum(torch.pow(u_W - (v + rv), 2), dim=-1)
        else:
            sqdist = torch.sum(torch.pow(u - (v + rv), 2), dim=-1)

        neg_sqdist = -sqdist
        
        if self.transe_enable_bias:
            if "subject" in self.transe_bias_mode:
                neg_sqdist += self.bs[u_idx]
            if "object" in self.transe_bias_mode:
                neg_sqdist += self.bo[v_idx]
        
        
        if self.distmult_score_function:
            u_W = u * Ru
            
            if self.distmult_sqdist:
                score = 2*torch.sum(u_W * v, dim=-1)
                if "subject" in self.distmult_sqdist_mode:
                    score -= torch.sum(u_W * u_W, dim=-1) 
                if "object" in self.distmult_sqdist_mode:
                    score -= torch.sum(v*v, dim=-1)
            else:
                score = torch.sum(u_W * v, dim=-1)
                
            if self.transe_enable_bias:
                if "subject" in self.transe_bias_mode:
                    score += self.bs[u_idx]
                if "object" in self.transe_bias_mode:
                    score += self.bo[v_idx]
            
            return score
        else:
            return neg_sqdist
