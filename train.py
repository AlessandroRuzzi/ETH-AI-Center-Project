#TODO Setup parameters in config files
#TODO Setup ReadME

from pykeen.pipeline import pipeline
from pykeen.nn.init import PretrainedInitializer
import w2v

dataset_name = "WN18RR"

embedding_dim = 200

fasttext_entity_initializer = PretrainedInitializer(w2v.get_emb_matrix("word_vectors/cc.en.200.bin", embedding_dim, sub_word=True, dataset_name=dataset_name))

glove_entity_initializer = PretrainedInitializer(w2v.get_emb_matrix("word_vectors/glove-wiki-gigaword-200.bin", embedding_dim, sub_word=False, dataset_name=dataset_name))

run_name = f"glove_{embedding_dim}_{dataset_name}"

pipeline_result = pipeline(
     dataset='wn18rr',
     random_seed=20,
     dataset_kwargs = dict(
      create_inverse_triples = True
     ),
     model='TuckER',
     model_kwargs=dict(
        embedding_dim = embedding_dim,
        relation_dim = 30,
        dropout_0 = 0.2,
        dropout_1 = 0.2,
        dropout_2 = 0.3,
        apply_batch_normalization = True,
        entity_initializer = glove_entity_initializer,
        relation_initializer = "xavier_normal",
     ),
     optimizer = 'Adam',
     optimizer_kwargs = dict(
         lr = 0.01,
     ),
     lr_scheduler='ExponentialLR',
     lr_scheduler_kwargs=dict(
         gamma=1.0,
     ),
     loss='bceaftersigmoid',
     loss_kwargs=dict(
         reduction = 'mean',
     ),
     training_loop='LCWA',
     training_kwargs=dict(
       num_epochs=500,
       batch_size = 128,
       #checkpoint_name='my_checkpoint.pt',
       #checkpoint_frequency=50,
       #checkpoint_directory='checkpoints',
       label_smoothing = 0.1
    ),
     evaluator_kwargs=dict(
         filtered = True,
     ),
     metadata= dict(
        title = run_name,
    ),
     result_tracker='wandb',
     result_tracker_kwargs=dict(
        project='W2V_for_KGs',
        entity = 'eth_ai_center_kg_project',
     ),
)


pipeline_result.save_to_directory(f'results/{run_name}')
