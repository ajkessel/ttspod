import os
from whisperspeech.pipeline import Pipeline
import torch
models=os.listdir('models')
text="The attacks in Lebanon required getting deep into the supply chain, which is difficult to do. But the sabotage contributes to a sense of vulnerability that ordinary devices can become a source of danger."
torch.cuda.empty_cache()
for i,model in enumerate(models):
    print(f'checking model {model}')
    try:
        if "t2s" in model:
            pipe = Pipeline(t2s_ref=f'./models/{model}', device = "cuda", optimize = True)
        elif "s2a" in model:
            pipe = Pipeline(s2a_ref=f'./models/{model}', device = "cuda", optimize = True)
        else:
            continue
    except Exception as e:
        print(f'failed with {e}')
    try:
        pipe.generate_to_file(f'out/{i}.mp3',text)
    except Exception as e:
        print(f'failed with {e}')
    torch.cuda.empty_cache()
for i,model in enumerate(models):
    print(i,model)
