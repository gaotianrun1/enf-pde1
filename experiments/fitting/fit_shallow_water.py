import hydra
from omegaconf import DictConfig
import omegaconf
import wandb

import jax.numpy as jnp

from experiments.fitting.datasets import get_dataloader
from experiments.fitting.trainers.pde_trainer import MetaSGDPDETrainer

from experiments.fitting import get_model_pde


@hydra.main(version_base=None, config_path=".", config_name="config_shallow_water")
def train(cfg: DictConfig):

    # Set log dir
    if not cfg.logging.log_dir:
        hydra_cfg = hydra.core.hydra_config.HydraConfig.get()
        cfg.logging.log_dir = hydra_cfg['runtime']['output_dir']

    assert cfg.dataset.name == "shallow_water_low_res", "Dataset must be shallow_water_low_res for this experiment."

    # Create the dataset, this is a low-res version of shallow-water
    trainset, testset = get_dataloader(dataset_cfg=cfg.dataset)

    sample_batch = next(iter(trainset))
    smp_image = sample_batch[0][0]
    image_shape = smp_image.shape
    cfg.dataset.image_shape = image_shape

    # coordinate grid over sphere
    coords = jnp.array(trainset.dataset.dataset.coords)

    # Set dimensionality of input and output
    cfg.nef.num_in = 2
    cfg.nef.num_out = image_shape[-1]

    # Initialize wandb
    wandb.init(
        project=cfg.proj_name,
        dir=cfg.logging.log_dir,
        config=omegaconf.OmegaConf.to_container(cfg),
        mode='disabled' if cfg.logging.debug else 'online',
    )

    # Get nef and autodecoders
    nef, ode_model = get_model_pde(cfg)

    trainer = MetaSGDPDETrainer(
        nef=nef,
        ode_model=ode_model,
        config=cfg,
        train_loader=trainset,
        val_loader=testset,
        coords=coords,
        seed=cfg.seed,
    )

    trainer.create_functions()

    # Train model
    final_state = trainer.train_model(cfg.training.num_epochs)

    # Create shallow water hi-res dataset
    cfg.dataset.name = "shallow_water"
    trainset, testset = get_dataloader(dataset_cfg=cfg.dataset)

    sample_batch = next(iter(trainset))
    smp_image = sample_batch[0][0]
    image_shape = smp_image.shape
    cfg.dataset.image_shape = image_shape

    # coordinate grid over sphere
    coords = jnp.array(trainset.dataset.dataset.coords)

    hi_res_trainer = MetaSGDPDETrainer(
        nef=nef,
        ode_model=ode_model,
        config=cfg,
        train_loader=trainset,
        val_loader=testset,
        coords=coords,
        seed=cfg.seed,
    )

    hi_res_trainer.create_functions()

    # Validate model
    hi_res_trainer.validate_epoch(final_state)


if __name__ == "__main__":
    train()
