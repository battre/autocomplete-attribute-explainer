# Address modelling

This directory contains a bunch of [YAML](https://yaml.org/) files to prototype
the modelling of addresses.

`countries/global` contains a model prototype that is then adapted by overrides
in `countries/??`.

Executing `python3 main.py` reads all configuration data and renders it to
HTML in the output directory `out`.

## Configuration files

`countries/*/*-metadata.yaml` contains some metadata about a country. It
contains a dictionary with the following keys:
* `country` stores the two digit country code of the country.
* `flag` stores a UTF-8 flag.
* `overview` contains HTML code that is rendered to the output for the country
  at the top.

`countries/global/global-model.yaml` contains a hierarchy that can serve
as a prototype for an address hierarchy.

`countries/??/??-model.yaml` modifies the `global-model.yaml` configuration:
* `extra-definitions` allows adding new tokens to the hierarchy or overriding
  existing ones. It's a dictionary where the key represents the token and
  the value is a list of children of the token.
* `append-after` is a dictionary that contains anchor points as keys and the
  list of extra-definitions to be added after this anchor point.
* `cut-off-tokens` contains a list of tokens that will be removed from the
  address hierarchy.
* `cut-off-children` contains a list of tokens whose children will be removed
  from the address hierarchy.
* `synthesized-nodes` follows the same structure as `extra-definitions`, but
  the added tokens are designated as synthesized nodes. These are nodes that
  live outside the main hierarchy. They don't have to be stored in the model.
  Instead their value can be formatted from their children. They are injected
  into the model at the position of the lowest common ancestor of all children.

`countries/*/*-descriptions.yaml` contains labels for the tokens.

## Output

The script generates one output file per country. Each output fill is structured
as follows:
* Country preamble (overview for the metadata file)
* Hierachical overview of the field types in the country ("index")
* Details about the concept/token
* Epilogue per country (any module gets the chance to append more data)

## Modules

The program is structured by a set of modules which can parse config files
and/or generate output.

`modules/abstract_module.py` contains the base class for all modules. Each
module can do the following operations in the following order:
* Observe all config files and decide whether the module wants to process
  a config file (based on the name). Optionally store data in `Renderer`.
* Generate a preamble
* Generate the hierarchical overview
* For each concept/token, add details to the details section
* Generate an epilogue

The modules have a fixed order which is defined in `main.py`. This guarantees
that read operations can happen before output generation for example.

## Check type information
Run `pytype .` to verify that all type annotations are correct.

## Code formatting
Run `yapf -i -r .` before checking in code using
[yapf](https://github.com/google/yapf).

## Running unittests
Run `python3 -m unittest discover -p "*_test.py"` to execute unittests.
