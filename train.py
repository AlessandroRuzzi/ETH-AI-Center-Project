from pykeen.pipeline import pipeline
from pykeen.nn.init import PretrainedInitializer
from bert_embs import get_bert_embeddings, get_bert_embeddings_relation
from data_relation_init import get_data_relation_matrix
import w2v
import json
import argparse
import pathlib
from typing import Union, List
from sklearn.preprocessing import normalize
import torch
import yaml
import pdb
from typing import (
    Any,
    Mapping,
    Union,
)
import os
import dotenv
import random
import numpy as np

# Load environment variables from `.env`.
dotenv.load_dotenv(override=True)


def str2bool(v):
    if isinstance(v, bool):
        return v
    if v.lower() in ("yes", "true", "t", "y", "1"):
        return True
    elif v.lower() in ("no", "false", "f", "n", "0"):
        return False
    else:
        raise argparse.ArgumentTypeError("Boolean value expected.")


def set_all_seeds(seed_num):
    print(f"[ Using seed : {seed_num} ]")
    torch.manual_seed(seed_num)
    torch.cuda.manual_seed_all(seed_num)
    torch.cuda.manual_seed(seed_num)
    random.seed(seed_num)
    np.random.seed(seed_num)


def load_configuration(
    path: Union[str, pathlib.Path, os.PathLike]
) -> Mapping[str, Any]:
    """Load a configuration from a JSON or YAML file."""

    path = pathlib.Path(path)
    if path.suffix == ".json":
        with path.open() as file:
            return json.load(file)

    if path.suffix in {".yaml", ".yml"}:
        with path.open() as file:
            return yaml.safe_load(file)

    raise ValueError(
        f"Unknown configuration file format: {path.suffix}. Valid formats: json, yaml"
    )

def get_relation_matrix_initializer(
     init: str, model_name,embedding_dim, dataset_name, config, vectors_dir="word_vectors", bert_layer=[-1]):
    """Get the Relation matrix embeddings initializer."""

    if init == "glove":
        emb_matrix =  w2v.get_emb_matrix_relation(
                f"{vectors_dir}/glove-wiki-gigaword-{embedding_dim}.bin",
                embedding_dim,
                sub_word=False,
                dataset_name=dataset_name,
            )

        relation_initializer = PretrainedInitializer(
          emb_matrix # not sure here
        )

    elif init == "bert":
        emb_matrix = get_bert_embeddings_relation(
            layers=bert_layer,
            dataset_name=dataset_name,
            bert_model="prajjwal1/bert-mini"
        )
        relation_initializer = PretrainedInitializer(
          emb_matrix # not sure here
        )
    else:
        relation_initializer = config["pipeline"]["model_kwargs"]["relation_matrix_initializer"]
    return relation_initializer


def get_relation_initializer(
     init: str, model_name,embedding_dim, dataset_name, config, vectors_dir="word_vectors", bert_layer=[-1]):
    """Get the Relation embeddings initializer."""
    if args.use_data_relation_init:
        relation_initializer = PretrainedInitializer(
            get_data_relation_matrix(model_name, dataset_name, init)
        )
    else: 
        if init == "glove":
            emb_matrix =  w2v.get_emb_matrix_relation(
                    f"{vectors_dir}/glove-wiki-gigaword-{embedding_dim}.bin",
                    embedding_dim,
                    sub_word=False,
                    dataset_name=dataset_name,
                )
            if model_name == "tucker":
                emb_matrix = emb_matrix.repeat(2,1)
            relation_initializer = PretrainedInitializer(
            emb_matrix # not sure here
            )
            
        elif init == "bert":
            emb_matrix = get_bert_embeddings_relation(
                layers=bert_layer,
                dataset_name=dataset_name,
                bert_model="prajjwal1/bert-mini"
            )
            if model_name == "tucker":
                emb_matrix = emb_matrix.repeat(2,1)
            relation_initializer = PretrainedInitializer(
            emb_matrix # not sure here
            )
        else:
            relation_initializer = config["pipeline"]["model_kwargs"]["relation_initializer"]

    return relation_initializer


def get_entity_initializer(
    init: str, embedding_dim, dataset_name, config, vectors_dir="word_vectors", bert_layer=-1, bert_weigh=False, bert_desc=False, bert_layer_weights=None
):
    """Get an Entity embeddings initializer."""

    if init == "fasttext":
        entity_matrix = w2v.get_emb_matrix(
            f"{vectors_dir}/cc.en.{embedding_dim}.bin",
            embedding_dim,
            sub_word=True,
            dataset_name=dataset_name,
        )

        if args.normalize_entity_mtx:
            entity_matrix = normalize(entity_matrix, axis=1)
            entity_matrix = torch.from_numpy(entity_matrix.astype(np.float32))

        entity_matrix = entity_matrix * args.mure_mult_factor

        entity_initializer = PretrainedInitializer(
            entity_matrix
        )
    elif init == "w2v":
        entity_matrix = w2v.get_emb_matrix(
            f"{vectors_dir}/word2vec-google-news-{embedding_dim}.bin",
            embedding_dim,
            sub_word=False,
            dataset_name=dataset_name,
        )

        if args.normalize_entity_mtx:
            entity_matrix = normalize(entity_matrix, axis=1)
            entity_matrix = torch.from_numpy(entity_matrix.astype(np.float32))

        entity_matrix = entity_matrix * args.mure_mult_factor

        entity_initializer = PretrainedInitializer(
            entity_matrix
        )
    elif init == "glove":
        entity_matrix = w2v.get_emb_matrix(
            f"{vectors_dir}/glove-wiki-gigaword-{embedding_dim}.bin",
            embedding_dim,
            sub_word=False,
            dataset_name=dataset_name,
        )

        if args.normalize_entity_mtx:
            entity_matrix = normalize(entity_matrix, axis=1)
            entity_matrix = torch.from_numpy(entity_matrix.astype(np.float32))

        entity_matrix = entity_matrix * args.mure_mult_factor

        entity_initializer = PretrainedInitializer(
            entity_matrix
        )
    elif init == "bert":
        entity_matrix = get_bert_embeddings(
            layers=bert_layer,
            layer_weights=bert_layer_weights,
            dataset_name=dataset_name,
            bert_model="prajjwal1/bert-mini",
            use_entity_descriptions=bert_desc,
            weigh_mean=bert_weigh,
            entity_and_relation_input=args.bert_entity_and_relation
        )

        if args.normalize_entity_mtx:
            entity_matrix = normalize(entity_matrix, axis=1)
            entity_matrix = torch.from_numpy(entity_matrix.astype(np.float32))
        
        entity_matrix = entity_matrix * args.mure_mult_factor

        entity_initializer = PretrainedInitializer(entity_matrix)
    else:
        entity_initializer = config["pipeline"]["model_kwargs"]["entity_initializer"]
    return entity_initializer


def pipeline_from_config(
    dataset_name: str,
    model_name: str,
    init: str,
    embdim: int,
    epochs: int,
    vectors_dir: str,
    random_seed: int,
    wandb_group: str,
    bert_layer: List[int],
    bert_layer_weights: List[float],
    bert_stem: bool,
    bert_desc: bool,
    dropout_0: float,
    dropout_1: float,
    dropout_2: float,
    relation_init: str,
    relation_matrix_init: str,
):
    """Initialize pipeline parameters from config file."""

    config_path = f"./config/{model_name.lower()}_{dataset_name.lower()}.json"
    config = load_configuration(config_path)

    if embdim is None:
        embedding_dim = config["pipeline"]["model_kwargs"]["embedding_dim"]
    else:
        embedding_dim = embdim

    if epochs is None:
        num_epochs = config["pipeline"]["training_kwargs"]["num_epochs"]
    else:
        num_epochs = epochs

    if dropout_0:
        config["pipeline"]["model_kwargs"]["dropout_0"] = dropout_0

    if dropout_1:
        config["pipeline"]["model_kwargs"]["dropout_1"] = dropout_1

    if dropout_2:
        config["pipeline"]["model_kwargs"]["dropout_2"] = dropout_2

    relation_initializer = get_relation_initializer(
        relation_init, model_name, embedding_dim, dataset_name, config, vectors_dir, bert_layer)
    entity_initializer = get_entity_initializer(
        init, embedding_dim, dataset_name, config, vectors_dir, bert_layer, bert_stem, bert_desc, bert_layer_weights,
    )
    
    if random_seed is not None:
        config["pipeline"]["random_seed"] = random_seed

    config["pipeline"]["model_kwargs"]["entity_initializer"] = entity_initializer
    config["pipeline"]["model_kwargs"]["relation_initializer"] = relation_initializer
    if relation_init and model_name not in ["mure", "distmult","transe"]:
        config["pipeline"]["model_kwargs"]["relation_dim"] = embedding_dim
    config["pipeline"]["model_kwargs"]["embedding_dim"] = embedding_dim
    config["pipeline"]["training_kwargs"]["num_epochs"] = num_epochs

    if model_name == "mure":
        relation_matrix_initializer = get_relation_matrix_initializer(relation_matrix_init, model_name, embedding_dim, dataset_name, config, vectors_dir, bert_layer)
        config["pipeline"]["model_kwargs"]["relation_matrix_initializer"] = relation_matrix_initializer


    if model_name == "mure":
        if init == "baseline":
            config["pipeline"]["model_kwargs"]["entity_initializer_kwargs"] = dict(std=args.mure_mult_factor)
        if relation_init == None:
            config["pipeline"]["model_kwargs"]["relation_initializer_kwargs"] = dict( std=1.0e-03,)
        if relation_matrix_init == None:
            config["pipeline"]["model_kwargs"]["relation_matrix_initializer_kwargs"] = dict(a=-1,b=1,)

    run_name = f"{init}_{embedding_dim}_{model_name}_{dataset_name}"

    pipeline_kwargs = config["pipeline"]
    pipeline_result = pipeline(
        metadata=dict(
            title=run_name,
        ),
        result_tracker="wandb",
        result_tracker_kwargs=dict(
            project="W2V_for_KGs", entity="eth_ai_center_kg_project", group=wandb_group
        ),
        **pipeline_kwargs,
    )

    pipeline_result.save_to_directory(f"results/{run_name}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dataset",
        type=str,
        default="wn18rr",
        nargs="?",
        help="Which dataset to use: fb15k237 or wn18rr.",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="tucker",
        nargs="?",
        help="Which model to train: tucker",
    )
    parser.add_argument(
        "--init",
        type=str,
        default="baseline",
        nargs="?",
        help="How to initialise embeddings: baseline, w2v, fasttext, glove, bert",
    )
    parser.add_argument(
        "--relation_init",
        type=str,
        default=None,
        nargs="?",
        help="How to initialise relation embeddings: baseline, glove, bert",
    )
    parser.add_argument(
        "--relation_matrix_init",
        type=str,
        default=None,
        nargs="?",
        help="How to initialise relation matrix mure: baseline, glove, bert",
    )
    parser.add_argument(
        "--use_data_relation_init",
        action="store_true",
        help="initialize relation vectors as average of scoring function wrt entities"
    )
    parser.add_argument(
        "--embdim",
        type=int,
        default=None,
        nargs="?",
        help="Dimension of embedding vectors, if None then embedding_dim in the .json file will be used",
    )
    parser.add_argument(
        "--epochs",
        type=int,
        default=None,
        nargs="?",
        help="Number of epochs to train the model for",
    )
    parser.add_argument(
        "--vectors_dir",
        type=str,
        default="word_vectors",
        nargs="?",
        help="Directory where vectors are stored",
    )
    parser.add_argument(
        "--random_seed",
        type=int,
        default=17,
        nargs="?",
        help="Random seed for the pipeline",
    )
    parser.add_argument(
        "--wandb_group",
        type=str,
        default=None,
        nargs="?",
        help="Group name for wandb runs",
    )
    parser.add_argument(
        "--bert_layer",
        default=[0],
        nargs="+",
        help="BERT layer to take embeddings from",
    )
    parser.add_argument(
        "--bert_layer_weight_1",
        default=None,
        type=float,
        nargs="?",
        help="weights for first bert_layer to computer weighted average",
    )
    parser.add_argument(
        "--bert_layer_weight_2",
        default=None,
        type=float,
        nargs="?",
        help="weights for second bert_layer to computer weighted average",
    )
    parser.add_argument(
        "--bert_layer_weight_3",
        default=None,
        type=float,
        nargs="?",
        help="weights for third bert_layer to computer weighted average",
    )
    parser.add_argument(
        "--bert_stem_weighted",
        action="store_true",
        help="weight BERT tokens using stemming",
    )
    parser.add_argument(
        "--bert_desc",
        action="store_true",
        help="use entity descriptions to init BERT embs",
    )
    parser.add_argument(
        "--bert_entity_and_relation",
        action="store_true",
        help="Use both entity name and relation name as input to get entity embedding from bert",
    )
    parser.add_argument(
        "--dropout_0",
        type=float,
        default=None,
        nargs="?",
        help="Dropout rate on TuckER core tensor",
    )
    parser.add_argument(
        "--dropout_1",
        type=float,
        default=None,
        nargs="?",
        help="Dropout rate on ...",
    )
    parser.add_argument(
        "--dropout_2",
        type=float,
        default=None,
        nargs="?",
        help="Dropout rate on ...",
    )
    parser.add_argument(
        "--normalize_entity_mtx",
        type=str2bool,
        default=False,
        help="Normalize every entity vector to L2-norm=1",
    )
    parser.add_argument(
        "--mure_mult_factor",
        type=float,
        default=1,
        help="Constant factor that is multiplied to the entity matrix (in MuRE)"
    )

    args = parser.parse_args()

    args.bert_layer = [int(x) for x in args.bert_layer]

    set_all_seeds(args.random_seed)

    bert_layer_weights = []
    if args.bert_layer_weight_1 is not None:
        bert_layer_weights.append(args.bert_layer_weight_1)
    if args.bert_layer_weight_2 is not None:
        bert_layer_weights.append(args.bert_layer_weight_2)
    if args.bert_layer_weight_3 is not None:
        bert_layer_weights.append(args.bert_layer_weight_3)
    
    if args.bert_layer is not None:
        args.bert_layer = [int(x) for x in args.bert_layer]
    if len(bert_layer_weights) > 0:
        bert_layer_weights = [float(x) for x in bert_layer_weights]

        assert(len(args.bert_layer) > 1)
        assert(len(args.bert_layer) == len(bert_layer_weights))

        args.bert_layer_weights = bert_layer_weights
    else:
        args.bert_layer_weights = None
    

    pipeline_from_config(
        args.dataset,
        args.model,
        args.init,
        args.embdim,
        args.epochs,
        args.vectors_dir,
        args.random_seed,
        args.wandb_group,
        args.bert_layer,
        args.bert_layer_weights,
        args.bert_stem_weighted,
        args.bert_desc,
        args.dropout_0,
        args.dropout_1,
        args.dropout_2,
        args.relation_init,
        args.relation_matrix_init,
    )
