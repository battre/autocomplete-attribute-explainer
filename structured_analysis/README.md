# Structured analysis

While the analysis in [country_analysis.md](../country_analysis.md) has been
very useful, it is a bit hard to automatically process the data. This is a new
attempt to represent the information in a more machine readable way.

## General idea

The general idea of this approach is that we have a language described in
[src/address.proto](src/address.proto) with the following components:

* Concepts: These are the building blocks, the tokens in the
  [autocomplete-spec](https://html.spec.whatwg.org/multipage/form-control-infrastructure.html#autofill).
* SiteExamples: As the whole effort intends to represent real-world websites,
  it is useful to extract form structures from real-world websites. Each site
  example represents one such site.

## Instructions for generating a summary

You can summarize all information from various countries via the following
commands:

```bash
python3 -m pip install -r requirements.txt
./generate_protos.sh
./generate_html.sh
```

You can extract all fields (form controls) from an html file via the following
commands:

```base
gcloud config set project $PROJECT_NAME
gcloud auth application-default login
python3 -m pip install -r requirements.txt
./generate_protos.sh
python3 src/extract_fields.py --country=EN --language=ja file.html > out.textproto
```

## Result

You can find the result of the data analysis [here](https://battre.github.io/autocomplete-attribute-explainer/). Note that this is work in progress and not
as comprehensive as the initial [country_analysis.md](../country_analysis.md).