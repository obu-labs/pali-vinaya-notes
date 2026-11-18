# The Vinaya of the Pāli Canon Markdown Notes Generator

This repository contains code for pulling the Pāli Vinaya data from the
SuttaCentral API and generating a folder of interlinked markdown notes.

This folder is a Vinaya Notes Module (VNM) meant to work with the
[Bhante Suddhaso notes module](https://github.com/obu-labs/suddhaso-vinaya-notes/)
and the
[Ajahn Brahmali notes module](https://github.com/obu-labs/brahmali-vinaya-notes/).
For more information about the project, see
[The Vinaya Notebook homepage](https://labs.buddhistuniversity.net/vinaya).

To run the generator:
```sh
pip install -r requirements.txt
sh downloaddeps.sh
python3 generate.py "Canon (Pali)"
```

The generated notes will be found in the `Canon (Pali)` folder
or whatever folder you set as the argument to the script.

## Code

- `generate.py` runs everything.
- `suttacentral.py` fetches and renders the Pātimokkha rules and their Vibhaṅga.
- `khandhakas/` renders the Khandhakas. Its docstring walks through the steps.
- `utils/` has the helpers which aren't specific to either.

The `khandhakas` and `utils` packages have unit tests, which need neither the
network nor the files from `downloaddeps.sh`:
```sh
pip install pytest
pytest
```
