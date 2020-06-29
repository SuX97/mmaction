from abc import ABCMeta, abstractmethod

import torch.nn as nn
import torch.nn.functional as F

from ...apis import parse_losses
from .. import builder


class BaseRecognizer(nn.Module, metaclass=ABCMeta):
    """Base class for recognizers.

    All recognizers should subclass it.
    All subclass should overwrite:
        Methods:`forward_train`, supporting to forward when training.
        Methods:`forward_test`, supporting to forward when testing.

    Args:
        backbone (dict): Backbone modules to extract feature.
        cls_head (dict): Classification head to process feature.
        train_cfg (dict): Config for training. Default: None.
        test_cfg (dict): Config for testing. Default: None.
    """

    def __init__(self, backbone, cls_head, train_cfg=None, test_cfg=None):
        super().__init__()
        self.backbone = builder.build_backbone(backbone)
        self.cls_head = builder.build_head(cls_head)

        self.train_cfg = train_cfg
        self.test_cfg = test_cfg
        self.init_weights()

    def init_weights(self):
        self.backbone.init_weights()
        self.cls_head.init_weights()

    def extract_feat(self, imgs):
        x = self.backbone(imgs)
        return x

    def average_clip(self, cls_score):
        """Averaging class score over multiple clips.

        Using different averaging types ('score' or 'prob' or None,
        which defined in test_cfg) to computed the final averaged
        class score.

        Args:
            cls_score (torch.Tensor): Class score to be averaged.

        return:
            torch.Tensor: Averaged class score.
        """
        if 'average_clips' not in self.test_cfg.keys():
            raise KeyError('"average_clips" must defined in test_cfg\'s keys')

        average_clips = self.test_cfg['average_clips']
        if average_clips not in ['score', 'prob', None]:
            raise ValueError(f'{average_clips} is not supported. '
                             f'Currently supported ones are '
                             f'["score", "prob", None]')

        if average_clips == 'prob':
            cls_score = F.softmax(cls_score, dim=1).mean(dim=0, keepdim=True)
        elif average_clips == 'score':
            cls_score = cls_score.mean(dim=0, keepdim=True)
        return cls_score

    @abstractmethod
    def forward_train(self, imgs, labels):
        pass

    @abstractmethod
    def forward_test(self, imgs):
        pass

    def forward(self, imgs, label=None, return_loss=True):
        if return_loss:
            if label is None:
                raise ValueError('Label should not be None.')
            return self.forward_train(imgs, label)
        else:
            return self.forward_test(imgs)

    def train_step(self, data_batch, optimizer, **kwargs):
        imgs = data_batch['imgs']
        label = data_batch['label']

        losses = self.forward(imgs, label)

        loss, log_vars = parse_losses(losses)

        outputs = dict(
            loss=loss,
            log_vars=log_vars,
            num_samples=len(next(iter(data_batch.values()))))

        return outputs

    def val_step(self, data_batch, optimizer, **kwargs):
        imgs = data_batch['imgs']

        results = self.forward(imgs, None, return_loss=False)

        outputs = dict(results=results)

        return outputs
