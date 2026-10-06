# Training notebook

`train.ipynb` fine-tunes Qwen2.5-0.5B-Instruct with LoRA on the training split, evaluates it on
the validation split, pushes the adapter to
[Khalid-Mehmood-117/qwen2.5-0.5b-ticket-triage-lora](https://huggingface.co/Khalid-Mehmood-117/qwen2.5-0.5b-ticket-triage-lora)
and reloads it from the Hub to prove the upload worked. It runs on the free Colab T4 GPU.

## Steps in Google Colab
1. **Open the notebook.** Go to https://colab.research.google.com, choose *File > Open notebook >
   GitHub*, paste `Khalid-Mehmood-117/fine-tuned-llm-ticket-triage` and pick `notebooks/train.ipynb`.
2. **Add the Hugging Face token as a secret.** Click the key icon in the left sidebar
   (*Secrets*), *Add new secret*, name it exactly `HF_TOKEN`, paste a Hugging Face token with
   **write** access as the value, and switch on *Notebook access*. Never paste the token into a
   cell.
3. **Select the T4 GPU.** *Runtime > Change runtime type > T4 GPU > Save*.
4. **Run all.** *Runtime > Run all*. If Colab asks to grant the notebook access to the
   `HF_TOKEN` secret, click *Grant access*. Nothing in the notebook needs editing; the settings
   cell at the top already has the right token secret name and adapter repo.
5. **Send back the result.** When the last cell finishes, copy the JSON summary it prints
   (training time, peak GPU memory, validation metrics) and send it to the repo owner. Do not
   save the notebook back to GitHub: the repo copy must stay without outputs.

## What to expect
| | Estimate |
|---|---|
| Whole notebook | about 20 to 30 minutes |
| Library install and model download | 2 to 4 minutes |
| Training (1,343 tickets, up to 3 epochs, about 1.2 million tokens) | about 10 to 20 minutes |
| Validation generation (169 tickets) | 1 to 3 minutes |
| Peak GPU memory | about 5 to 8 GB of the T4's 15 GB |

These are estimates; the notebook prints the measured training time and peak GPU memory.
Early stopping may end training after 2 epochs if validation loss stops improving.

## If something goes wrong
- **"No GPU found"**: the runtime is not T4. Repeat step 3, then *Run all* again.
- **"Could not read the Colab secret 'HF_TOKEN'"**: the secret is missing, misnamed or
  *Notebook access* is off. Repeat step 2.
- **401 or 403 when pushing**: the token is read-only. Create a write token at
  https://huggingface.co/settings/tokens and update the secret.
- **Colab disconnects**: free sessions can time out when idle. Keep the tab open and run again.

## Local smoke test (developers)
The same notebook runs on CPU with a tiny subset and no push, to check the code before Colab:
```bash
SMOKE_TEST=1 python -c "import json; nb=json.load(open('notebooks/train.ipynb', encoding='utf-8')); ns={}; [exec(''.join(c['source']), ns) for c in nb['cells'] if c['cell_type']=='code']"
```
