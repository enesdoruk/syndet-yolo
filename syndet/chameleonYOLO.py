import cv2
import torch
import wandb
import numpy as np
import torch.nn as nn
from scipy.ndimage import zoom
from mmengine.visualization import Visualizer

import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


from syndet.modules import  Detect
from syndet.backbone import Backbone
from syndet.head import Head
from syndet.FDL import FDL_loss

class DetectionModel(nn.Module):
    def __init__(self):
        super(DetectionModel, self).__init__()
        
        self.layers = []
        self.layers.append(Backbone())
        self.layers.append(Head())
        self.model = nn.Sequential(*self.layers)

        m = self.model[-1].detect 
        if isinstance(m, (Detect)):
            s = 256 
            m.inplace = True
            forward = lambda x:  self.forward(x)
            m.stride = torch.tensor([s / x.shape[-2] for x in forward(torch.zeros(1, 3, s, s))])  
            self.stride = m.stride
            m.bias_init() 
            
        self.flat = nn.Flatten()
        self.linear = nn.Linear(1024*20*20, 256)
        

    def forward(self, x, target=None, verbose=False, it=0, ep=0):      
        backb5, backb7, backb10 = self.model[0](x)
        
        if target is None:
            head, _ = self.model[1](backb5,
                                backb7, 
                                backb10)  
            return head
        
        else:
            backb5_t, backb7_t, backb10_t = self.model[0](target) 
            
            head_s, head_convs_s = self.model[1](backb5,
                                backb7, 
                                backb10)  
            
            head_t, head_convs_t  = self.model[1](backb5_t,
                                backb7_t, 
                                backb10_t)  
            
                
            if verbose:
                for i in range(x.shape[0]):
                    visualizer = Visualizer(vis_backends=[dict(type='LocalVisBackend')], save_dir=os.getcwd())
                    img = np.array(x[i].cpu(), dtype=np.uint8).transpose(1,2,0)
                    
                    feat_corr_b5 = zoom(backb5[i].to(torch.float32).cpu().detach().numpy(), (1, 8, 8), order=1)
                    feat_corr_b5 = torch.tensor(feat_corr_b5).to('cuda')
                    drawn_img_b5 = visualizer.draw_featmap(feat_corr_b5, img, channel_reduction='select_max')
                    
                    feat_corr_b7 = zoom(backb7[i].to(torch.float32).cpu().detach().numpy(), (1, 16, 16), order=1)
                    feat_corr_b7 = torch.tensor(feat_corr_b7).to('cuda')
                    drawn_img_b7 = visualizer.draw_featmap(feat_corr_b7, img, channel_reduction='select_max')
                    
                    feat_corr_b10 = zoom(backb10[i].to(torch.float32).cpu().detach().numpy(), (1, 32, 32), order=1)
                    feat_corr_b10 = torch.tensor(feat_corr_b10).to('cuda')
                    drawn_img_b10 = visualizer.draw_featmap(feat_corr_b10, img, channel_reduction='select_max')
                    
                    act_img = cv2.hconcat([drawn_img_b5, drawn_img_b7, drawn_img_b10]) 

                    images = wandb.Image(act_img, caption=f"epoch: {ep}, iteration: {it}, image: {i}")
                    wandb.log({"feature_map": images})
            
            return head_s, head_convs_s, head_convs_t
        
if __name__ == "__main__":
    source = torch.randn(1, 3, 640, 640).cuda()
    target = torch.randn(1, 3, 640, 640).cuda()
    
    model = DetectionModel().cuda()
    
    head, head_convs_s, head_convs_t  = model(source, target)
    
    import pdb; pdb.set_trace()
    
    
    
