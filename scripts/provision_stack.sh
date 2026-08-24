#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

usage() {
  cat <<'EOF'
Usage: provision_stack.sh <stack> [options]

Create a fresh environment for one software stack on a new machine.
This script is intended to be run later on the target machine, not in the current workspace.

Stacks:
  alphagenome   AlphaGenome API software
  gpn           Song Lab GPN package
  nt-jax        Classic NT + SegmentNT-family JAX stack (source install)
  ntv3-hf       NTv3 tutorial stack (Hugging Face Transformers + PyTorch)
  borzoi        Calico Borzoi stack (baskerville + borzoi + westminster)
  evo2-light    Evo 2 light install (7B-class workflow)
  evo2-full     Evo 2 full install inside an active conda environment

Options:
  --deploy-root DIR   Working root for environments and upstream clones.
                      Default: <repo>/.deploy
  --python BIN        Python executable to use for venv creation. Default: python3
  -h, --help          Show this help message.

Environment variables:
  JAX_INSTALL_CMD     Optional command for hardware-specific JAX installation.
                      The script exposes $VENV_PYTHON for convenience.
  BORZOI_TENSORFLOW_SPEC
                      TensorFlow package for Borzoi. Default on Linux:
                      tensorflow[and-cuda]==2.15.1
  TORCH_INSTALL_CMD   Required for evo2-light. Example:
                      TORCH_INSTALL_CMD='$VENV_PYTHON -m pip install torch==2.7.1 --index-url https://download.pytorch.org/whl/cu128'
EOF
}

create_venv() {
  local python_bin="$1"
  local venv_dir="$2"

  if [[ ! -d "$venv_dir" ]]; then
    "$python_bin" -m venv "$venv_dir"
  fi

  echo "$venv_dir/bin/python"
}

clone_if_missing() {
  local url="$1"
  local target="$2"

  if [[ -d "$target/.git" ]]; then
    echo "using existing clone: $target"
    return 0
  fi

  mkdir -p "$(dirname "$target")"
  git clone "$url" "$target"
}

checkout_tag() {
  local target="$1"
  local tag="$2"

  if git -C "$target" describe --tags --exact-match 2>/dev/null | grep -qx "$tag"; then
    echo "using existing tag $tag: $target"
    return 0
  fi

  git -C "$target" fetch --depth 1 origin "refs/tags/$tag:refs/tags/$tag"
  git -C "$target" checkout --detach "$tag"
}

stack=""
deploy_root="$REPO_ROOT/.deploy"
python_bin="python3"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --deploy-root)
      deploy_root="$2"
      shift 2
      ;;
    --python)
      python_bin="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      if [[ -z "$stack" ]]; then
        stack="$1"
        shift
      else
        echo "error: unexpected argument '$1'" >&2
        usage >&2
        exit 1
      fi
      ;;
  esac
done

if [[ -z "$stack" ]]; then
  usage >&2
  exit 1
fi

venv_root="$deploy_root/venvs"
src_root="$deploy_root/src"
mkdir -p "$venv_root" "$src_root"

case "$stack" in
  alphagenome)
    venv_dir="$venv_root/alphagenome"
    venv_python="$(create_venv "$python_bin" "$venv_dir")"
    if ! "$venv_python" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)'; then
      echo "error: alphagenome requires Python >= 3.10." >&2
      echo "hint: rerun with --python python3.10 (or newer)." >&2
      exit 2
    fi
    "$venv_python" -m pip install --upgrade pip setuptools wheel
    if clone_if_missing "https://github.com/google-deepmind/alphagenome.git" "$src_root/alphagenome"; then
      "$venv_python" -m pip install "$src_root/alphagenome"
    else
      echo "warn: failed to clone alphagenome from GitHub; falling back to package index install." >&2
      "$venv_python" -m pip install alphagenome
    fi
    echo "ready: alphagenome environment at $venv_dir"
    ;;
  gpn)
    venv_dir="$venv_root/gpn"
    venv_python="$(create_venv "$python_bin" "$venv_dir")"
    "$venv_python" -m pip install --upgrade pip setuptools wheel
    "$venv_python" -m pip install "git+https://github.com/songlab-cal/gpn.git"
    echo "ready: gpn environment at $venv_dir"
    ;;
  nt-jax)
    venv_dir="$venv_root/nt-jax"
    venv_python="$(create_venv "$python_bin" "$venv_dir")"
    if ! "$venv_python" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)'; then
      echo "error: nt-jax source install requires Python >= 3.10 in practice (upstream JAX constraints)." >&2
      echo "hint: rerun with --python python3.10 (or newer), or use stack ntv3-hf for NTv3 tutorial workflows." >&2
      exit 2
    fi
    "$venv_python" -m pip install --upgrade pip setuptools wheel
    if [[ -n "${JAX_INSTALL_CMD:-}" ]]; then
      VENV_PYTHON="$venv_python" bash -lc "$JAX_INSTALL_CMD"
    else
      "$venv_python" -m pip install "jax>=0.6,<0.7"
    fi
    clone_if_missing "https://github.com/instadeepai/nucleotide-transformer.git" "$src_root/nucleotide-transformer"
    # Upstream's unified metadata also pulls the unrelated NTv3/Torch training
    # stack. Keep this environment scoped to classic NT and SegmentNT JAX APIs.
    "$venv_python" -m pip install \
      "numpy<2" \
      "ml-dtypes>=0.5,<0.6" \
      "dm-haiku>=0.0.12" \
      jmp joblib einops regex requests huggingface-hub
    "$venv_python" -m pip install --no-deps "$src_root/nucleotide-transformer"
    "$venv_python" -c 'import jax; from nucleotide_transformer.pretrained import get_pretrained_segment_nt_model, get_pretrained_segment_enformer_model, get_pretrained_segment_borzoi_model; print("JAX devices:", jax.devices())'
    echo "ready: nt-jax environment at $venv_dir"
    ;;
  ntv3-hf)
    venv_dir="$venv_root/ntv3-hf"
    venv_python="$(create_venv "$python_bin" "$venv_dir")"
    "$venv_python" -m pip install --upgrade pip setuptools wheel
    "$venv_python" -m pip install \
      "transformers>=4.55,<5" \
      "huggingface_hub>=0.23,<1" \
      safetensors \
      torch \
      "numpy<2"
    echo "ready: ntv3-hf environment at $venv_dir"
    ;;
  borzoi)
    venv_dir="$venv_root/borzoi"
    venv_python="$(create_venv "$python_bin" "$venv_dir")"
    if ! "$venv_python" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)'; then
      echo "error: borzoi workflows are grounded on Python 3.10+ in this repository." >&2
      echo "hint: rerun with --python python3.10 (or newer)." >&2
      exit 2
    fi
    "$venv_python" -m pip install --upgrade pip wheel
    # Baskerville still imports pkg_resources, removed in Setuptools 81+.
    "$venv_python" -m pip install "setuptools==80.9.0" cython pysam
    "$venv_python" -m pip install "pybedtools==0.10.0" --no-build-isolation
    if [[ -n "${BORZOI_TENSORFLOW_SPEC:-}" ]]; then
      "$venv_python" -m pip install "$BORZOI_TENSORFLOW_SPEC"
    elif [[ "$(uname -s)" == "Linux" ]]; then
      "$venv_python" -m pip install 'tensorflow[and-cuda]==2.15.1'
    else
      "$venv_python" -m pip install 'tensorflow==2.15.1'
    fi
    clone_if_missing "https://github.com/calico/baskerville.git" "$src_root/baskerville"
    clone_if_missing "https://github.com/calico/borzoi.git" "$src_root/borzoi"
    clone_if_missing "https://github.com/calico/westminster.git" "$src_root/westminster"
    # Current Westminster requires NumPy 2.3+, which conflicts with the
    # TensorFlow 2.15 line required by the published Borzoi workflow.
    checkout_tag "$src_root/westminster" "v0.0.1"
    "$venv_python" -m pip install "$src_root/baskerville"
    "$venv_python" -m pip install "$src_root/borzoi"
    "$venv_python" -m pip install "$src_root/westminster"
    "$venv_python" -m pip install "setuptools==80.9.0"
    "$venv_python" -m pip check
    echo "ready: borzoi environment at $venv_dir"
    echo "note: some Borzoi scripts still expect BORZOI_DIR/BORZOI_HG38/BORZOI_MM10 style environment variables."
    ;;
  evo2-light)
    if [[ -z "${TORCH_INSTALL_CMD:-}" ]]; then
      echo "error: TORCH_INSTALL_CMD is required for evo2-light." >&2
      echo "example: TORCH_INSTALL_CMD='\$VENV_PYTHON -m pip install torch==2.7.1 --index-url https://download.pytorch.org/whl/cu128'" >&2
      exit 2
    fi
    venv_dir="$venv_root/evo2-light"
    venv_python="$(create_venv "$python_bin" "$venv_dir")"
    "$venv_python" -m pip install --upgrade pip setuptools wheel
    VENV_PYTHON="$venv_python" bash -lc "$TORCH_INSTALL_CMD"
    "$venv_python" -m pip install "flash-attn==2.8.0.post2" --no-build-isolation
    "$venv_python" -m pip install evo2
    echo "ready: evo2-light environment at $venv_dir"
    ;;
  evo2-full)
    if ! command -v conda >/dev/null 2>&1; then
      echo "error: conda must be installed for evo2-full." >&2
      exit 2
    fi
    if [[ -z "${CONDA_PREFIX:-}" ]]; then
      echo "error: activate a conda environment before running evo2-full." >&2
      exit 2
    fi
    conda install -y -c nvidia cuda-nvcc cuda-cudart-dev
    conda install -y -c conda-forge transformer-engine-torch=2.3.0
    python -m pip install "flash-attn==2.8.0.post2" --no-build-isolation
    python -m pip install evo2
    echo "ready: evo2-full installed into active conda environment $CONDA_PREFIX"
    ;;
  *)
    echo "error: unknown stack '$stack'" >&2
    usage >&2
    exit 1
    ;;
esac
