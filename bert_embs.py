import numpy as np
import torch
from transformers import AutoTokenizer, AutoModel, PretrainedConfig
from w2v import get_id_word_dict, get_id_description_dict
import pickle
from tqdm import tqdm
from pykeen.datasets import WN18RR


def get_word_idx(sent: str, word: str):
    return sent.split(" ").index(word)


def get_hidden_states(encoded, token_ids_word, model, layers):
    """Push input IDs through model. Stack and sum `layers` (last four by default).
    Select only those subword token outputs that belong to our word of interest
    and average them."""
    with torch.no_grad():
        output = model(**encoded)

    # Get all hidden states
    states = output.hidden_states
    # Stack and sum all requested layers
    output = torch.stack([states[i] for i in layers]).sum(0).squeeze()
    # Only select the tokens that constitute the requested word
    word_tokens_output = output[token_ids_word]

    return word_tokens_output.mean(dim=0)


def get_word_vector(sent, idx_list, tokenizer, model, layers):
    """Get a word vector by first tokenizing the input sentence, getting all token idxs
    that make up the word of interest, and then `get_hidden_states`."""
    encoded = tokenizer.encode_plus(sent, return_tensors="pt")

    token_ids_words = np.array([w_id in idx_list for w_id in encoded.word_ids()])

    return get_hidden_states(encoded, token_ids_words, model, layers)


def get_bert_embeddings(layers=[-1], dataset_name="WN18RR", bert_model="prajjwal1/bert-mini", use_entity_descriptions=False):
    dataset_name = dataset_name.lower()
    tokenizer = AutoTokenizer.from_pretrained(bert_model)
    model = AutoModel.from_pretrained(bert_model, output_hidden_states=True)

    model_config = PretrainedConfig.from_pretrained(bert_model)
    embedding_dim = model_config.hidden_size

    if dataset_name == "wn18rr":
        dataset = WN18RR()
    else:
        raise NotImplementedError("Dataset not implemented")

    entity_dict = dataset.training.entity_to_id

    entity_id_to_word = get_id_word_dict(dataset_name, sub_word=True)
    if use_entity_descriptions:
        entity_id_to_description = get_id_description_dict(dataset_name)

    emb_matrix = np.zeros((len(entity_dict), embedding_dim))

    for entity_id in tqdm(entity_dict):
        entity_emb_idx = entity_dict[entity_id]
        entity_name = entity_id_to_word[str(entity_id)]

        if use_entity_descriptions:
            input_sentence = f"{entity_name} : {entity_id_to_description[str(entity_id)]}"
        else:
            input_sentence = entity_name

        idx_list = [get_word_idx(input_sentence, word) for word in entity_name.split(" ")]
        emb = get_word_vector(input_sentence, idx_list, tokenizer, model, layers)

        emb_matrix[entity_emb_idx, :] = emb 
    
    emb_matrix = torch.from_numpy(emb_matrix.astype(np.float32))

    return emb_matrix



if __name__ == '__main__':
    OUTPUT_NAME = "bert-mini_embs.pickle"
    emb_matrix = get_bert_embeddings()

    with open(f'word_vectors/{OUTPUT_NAME}', 'wb') as handle:
        pickle.dump(emb_matrix, handle, protocol=pickle.HIGHEST_PROTOCOL)
