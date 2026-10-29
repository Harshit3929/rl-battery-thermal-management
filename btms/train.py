import hydra
from omegaconf import DictConfig
from btms.agents.sb3_train import train


@hydra.main(version_base=None,config_path='configs',config_name='config')
def main(cfg: DictConfig):
    train(cfg)


if __name__ == '__main__':
    main()
