# Setup, downloads, versions, and licenses

Use backend-specific environments. Record the resolved commit rather than trusting a moving branch. The pins below were resolved from official repositories on 2026-07-19; review upstream security notices and model cards before production use.

| Backend | Official source pin | License at source | Main download |
|---|---|---|---|
| SaProt | `westlake-repl/SaProt@e91e4858b55944523f1f8d385f7b96a0d3d34c1d` | MIT code; also review selected checkpoint model card | SaProt checkpoint directory plus Foldseek binary/database support |
| Foldseek | tag `10-941cd33` | GPL-3.0 project; verify packaged binary terms | Release binary or conda package |
| ThermoMPNN | `Kuhlman-Lab/ThermoMPNN@2b04fd370e399911b1fa5848112cc9013f084110` | MIT | Repository includes `models/thermoMPNN_default.pt` |
| ProteinMPNN | `dauparas/ProteinMPNN@8907e6671bfbfc92303b5f79c4b5e6ce47cdef57` | MIT | Repository includes vanilla/soluble/CA-only weights |
| ESM-IF1 | `facebookresearch/esm@2b369911bb5b4b0dda914521b9475cad1656b2ac` | MIT | `esm_if1_gvp4_t16_142M_UR50` weights downloaded by `fair-esm` loader |

## Reproducible setup sequence

Run the bundled setup planner first:

```bash
python scripts/setup_structure_mutation_env.py \
  --backend saprot --env-name s2f-saprot \
  --source-root external --mode plan --output setup-saprot.json
```

Review the JSON, then rerun with `--mode execute` only when network, disk, and environment creation are authorized. The setup script uses argument arrays rather than a shell, refuses a non-empty clone target, and logs each command. It does not silently accept model licenses.

## SaProt and Foldseek

Clone the pinned SaProt source, create Python 3.10 environment, then follow its pinned `requirements.txt`. Install Foldseek independently and record `foldseek version`. Download a specific Hugging Face checkpoint such as `westlake-repl/SaProt_650M_AF2` only after reviewing its model card; use a smaller checkpoint for a smoke test when appropriate. Full structure-aware scoring requires Foldseek-generated 3Di tokens. Confirm CUDA support before selecting the 650M checkpoint.

## ThermoMPNN

The official repository recommends creating from `environment.yaml`; its alternative path uses Python 3.10, PyTorch/PyTorch Lightning, joblib, OmegaConf, pandas, NumPy, tqdm, MMseqs2, wandb, and Biopython. GPU PyTorch can be installed incorrectly by the YAML, so verify `torch.cuda.is_available()` and record the installed CUDA build. `analysis/custom_inference.py` is the simplest official PDB site-saturation entrypoint. The repository's point-mutant weights are under `models/`.

## ProteinMPNN

Clone the pin and create a lightweight environment with compatible PyTorch and NumPy. Official weights are committed under `vanilla_model_weights/`, `soluble_model_weights/`, and `ca_model_weights/`. For mutation proxies, prefer `--conditional_probs_only` or `--conditional_probs_only_backbone`; `--score_only` returns sequence negative log probability, not ddG.

## ESM-IF1

Install a compatible `fair-esm`/repository environment and load `esm.pretrained.esm_if1_gvp4_t16_142M_UR50()`. With the setup planner, `--download-model` adds that official loader call and sets `TORCH_HOME` to the resolved `--cache-root`; plan mode records it without downloading. The official repository is archived, so pin source and environment. Use `examples/inverse_folding/score_log_likelihoods.py STRUCTURE FASTA --chain CHAIN --outpath CSV`. Do not install modern OpenFold extras unless the selected ESM operation needs them.

## Download and cache policy

- Place sources under a declared source root and model caches under a declared cache root; do not write checkpoints into the skill directory.
- Save URL/repository, revision, file name, byte size, checksum, download time, and license/model-card acknowledgment to the manifest.
- Use local-files-only/offline mode after caches are populated when reproducibility matters.
- Never place access tokens in commands, logs, JSON, or archived intermediates.
- A shared `s2f-test` environment is suitable for wrapper and fixture tests. Use isolated backend environments for heavy real inference when dependency pins conflict.
