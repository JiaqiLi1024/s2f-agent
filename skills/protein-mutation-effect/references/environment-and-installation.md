# Environment, installation, and downloads

Use s2f-test as a light integration environment, not as proof that every research repository can safely share dependencies.

    conda create -n s2f-test python=3.10 pip -y
    conda run -n s2f-test python -m pip install --upgrade pip
    conda run -n s2f-test python -m pip install pyyaml numpy pandas scipy scikit-learn

Run normalization, import, MSA-profile, ProteinGym-metric, and archive smoke tests there. Create model-specific environments from each component skill's setup reference for deep-learning execution:

- s2f-esm: ESM-1v/ESMC adapter dependencies and pinned checkpoints.
- s2f-saprot: SaProt plus the required Foldseek/3Di preprocessing revision.
- s2f-thermompnn: the ThermoMPNN repository revision, weights, and its tested PyTorch/PyG stack.
- s2f-inverse-folding: ProteinMPNN and ESM-IF1 revisions, or separate them if their PyTorch constraints conflict.
- s2f-poet: the exact PoET repository/release and its documented data preparation stack.

## Download policy

1. Run plan and input validation before any checkpoint or dataset download.
2. Record source URL/repository, revision or release, checkpoint ID, file size when known, SHA-256 when published or locally computed, license, and cache path.
3. Prefer official repositories, official package indexes, or the model author's published model hub organization.
4. Do not commit model weights, ProteinGym full datasets, AlphaMissense catalogues, credentials, or license-restricted databases into this repository.
5. Cache outside a run directory; link or reference cached assets in run_manifest.json.
6. Never print API or Hugging Face tokens. Do not assume model access if authentication or a license gate is unresolved.

## Verification levels

- static: skill validator, Python compilation, and CLI help.
- deterministic-light: normalizer, MSA profile, AlphaMissense fixture lookup, imported score alignment, ProteinGym toy metrics, and archive lifecycle.
- backend-smoke: one short sequence or structure through an actual model checkpoint.
- scientific-reproduction: pinned dataset, checkpoint, and published evaluation protocol.

Report the highest level actually completed for each backend. A light smoke test is not a reproduction of ProteinGym performance.
