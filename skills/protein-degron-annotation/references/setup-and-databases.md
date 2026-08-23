# Setup And Databases

Use this reference before installing optional software, downloading motif datasets, or submitting to hosted services.

## Dedicated Conda Environment

The bundled script uses only the Python standard library for local ELM TSV, DEGRONOPEDIA xlsx scanning, and built-in QCDPred scoring. A dedicated environment is still recommended when adding optional helpers such as `gget`, DIAMOND, pandas, or openpyxl:

```bash
conda create -n protein-degron python=3.11 -y
conda activate protein-degron
conda install -c conda-forge -c bioconda gget diamond pandas openpyxl requests -y
```

If `mamba` is available, it can replace `conda`. Keep this environment separate from InterProScan, eggNOG, IDR, localization, and conservation environments because their dependency pins may differ.

## Missing Conda Or Mamba

If neither `conda` nor `mamba` exists:

1. Ask the user whether to install Miniforge or Miniconda.
2. Confirm installation location, usually `$HOME/miniforge3` or `$HOME/miniconda3`.
3. Do not run installers silently.
4. Create the `protein-degron` environment after installation.

Use a Python virtual environment only when conda-style installation is blocked. The core script can still run with system Python if no optional packages are needed.

## QCDPred

The skill includes a native Python implementation of QCDPred scoring, so no QCDPred installation or database download is needed for normal use:

```bash
python skills/protein-degron-annotation/scripts/protein_degron_annotation.py \
  --fasta proteins.fa \
  --tools qcdpred \
  --outdir output/protein-degron-annotation/proteins_qcdpred
```

Implementation details:

- Model source: KULL-Centre `papers/2022/degron-predict-Johansson-et-al/QCDpred.py`.
- Model type: 17-aa peptide logistic regression trained on yeast quality-control degradation data.
- Runtime dependency: standard-library Python only in this wrapper.
- Default threshold: `--qcdpred-threshold 0.85`.
- Default interval expansion: `--qcdpred-padding 8` residues on both sides of positive center residues.

If the user has already run the original stand-alone script, import the raw five-column output:

```bash
python skills/protein-degron-annotation/scripts/protein_degron_annotation.py \
  --fasta proteins.fa \
  --tools qcdpred \
  --qcdpred-output idr_qcdpred.txt \
  --outdir output/protein-degron-annotation/proteins_qcdpred_import
```

The KULL-Centre `_2023_Tesei_IDRome/QCDPred/code/idr_degron_scores.r` script is an aggregation workflow: it runs `QCDpred.py`, reads columns `name`, `seq`, `score`, `aa`, and `resi`, then computes QCDPred average, median, and maximum per IDR. The skill ports that aggregation into Python summary columns.

## ELM Data

ELM provides classes, instances, interaction domains, downloads, and a hosted motif-prediction API. For degron recognition, prefer local scanning of ELM classes whose `ELMIdentifier` starts with `DEG_` plus ELM classes whose names or descriptions explicitly mention degrons.

Relevant public files:

```bash
curl -L -o elms_classes.tsv http://elm.eu.org/elms/elms_index.tsv
curl -L -o elm_instances.tsv 'http://elm.eu.org/instances.tsv?q=*&taxon=&instance_logic='
curl -L -o elm_instances.fasta 'http://elm.eu.org/instances.fasta?q=*&taxon=&instance_logic='
curl -L -o elm_interaction_domains.tsv http://elm.eu.org/interactiondomains.tsv
```

The script only requires `elms_classes.tsv` for local regex degron scanning. The instances files are useful when the agent needs ELM instance context, DIAMOND/gget ELM workflows, or follow-up orthology support.

ELM also documents a hosted API:

- UniProt query: `http://elm.eu.org/start_search/<uniprot_id>.tsv`
- Raw sequence query: `http://elm.eu.org/start_search/<sequence>`

Respect the documented API limits: UniProt queries no more than one every three minutes; raw sequence queries no more than one per minute. Raw sequence URLs may be truncated for sequences longer than 2000 amino acids. For batch use, use local TSV scanning or `gget setup elm` instead of hosted requests.

ELM data are distributed under the ELM Software License Agreement. Ask before downloading or redistributing, especially for commercial or shared deployments.

## gget ELM

`gget elm` can use local ELM files and DIAMOND to report:

- Orthologous proteins with experimentally validated ELM instances.
- Direct regex motif matches in the provided sequence.

Setup:

```bash
conda activate protein-degron
gget setup elm
```

Use gget when the user wants broader ELM motif context. Use the bundled degron script when the task is specifically a standardized degron-candidate TSV/JSON report.

## DEGRONOPEDIA Data

DEGRONOPEDIA provides a downloadable degron motif dataset:

```bash
curl -L -o DEGRONOPEDIA_degron_dataset.xlsx \
  https://degronopedia.com/degronopedia/download/data/DEGRONOPEDIA_degron_dataset.xlsx/
```

The `Degrons` sheet contains degron motif regexes, organism, location, references, UPS-recognizing components, additional notes, license, and whether each degron is free for any use. The bundled script parses this xlsx directly without openpyxl.

Ask before downloading. Record the download date and preserve the license columns in downstream reports. DEGRONOPEDIA states that licenses vary by degron and external datasets/tools may impose commercial restrictions.

## DEGRONOPEDIA Web Server

Use the web server when the user needs its full context: structure, disorder, conservation, PTM/mutation context, PSI, and tripartite degron model outputs.

Important constraints from the public FAQ and form:

- Query one protein at a time.
- FASTA input is documented for 50 to 40,000 canonical amino acids.
- Results can be downloaded as xlsx with separate sheets.
- No account is required.
- The complete server is not available for local deployment.
- ML PSI has a separate standalone software repository from the authors.

Do not pretend there is a stable public batch API unless the user provides one. If web results are needed, instruct the user to submit through the website, download xlsx results, then import them into the report workflow.

## Reproducibility

Record:

- ELM class download date/version from the file header.
- DEGRONOPEDIA dataset download date and file checksum.
- Query sequence checksum and coordinate convention.
- Regex source and motif database.
- Whether hits came from local regex scan, ELM hosted API, gget ELM, DEGRONOPEDIA dataset, DEGRONOPEDIA web xlsx, QCDPred native scoring, imported QCDPred output, or custom motifs.
