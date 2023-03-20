# Proposal for extending the autocomplete attribute

**Written**: 2022-01-28, **Updated**: 2023-03-13

## tl;dr

This is a proposal to extend the [autocomplete attribute] in HTML to match the
structures of address forms we can observe on today's web.

A companion feature request exists at https://github.com/whatwg/html/issues/4986

Today's [autocomplete attribute] provides an opinionated list of field names
that prescribe how to structure an address/credit card form in order to be
compatible with autofilling by the user agent. In particular it assumes a
structure containing elements like
* `name`
* `street-address` (optionally broken down into `address-line1`,
  `address-line2`, `address-line3`)
* `address-level4` ... `address-level1`
* `postal-code`
* `country`

This way of structuring address formats is not representative for many address
forms that can be observed on the internet around the world today. For example,
in many countries it is common to have specific fields asking for a street name
and a house number. More examples of field types that are not supported by the
autofill attribute follow below.

This document proposes a second, alternative, way of describing addresses.

## Naming

We refer to today's address representation via the [autocomplete attribute] as
**unstructured addresses** because the `street-address`
or the corresponding `address-lineX` entries don't assume a lot of semantics
in the `<input>` form controls. These addresses can be interpreted well by
humans but not so well by computers.

This document proposes an additional way of describing addresses that we refer
to as **structured addresses** in which the individual components that would
go into a street-address can be referenced individually, e.g. the street name,
house number, apartment number, building name, delivery instructions, etc.

## Metrics and impact

The [Country
Analysis](https://battre.github.io/autocomplete-attribute-explainer/index.html)
looked at 26 different countries and identified that only a small minority of
countries is well covered by today's autocomplete attribute.

## The case for adding new field types

Our arguments for adding the new autocomplete types (“Field names” in the HTML
Spec) are:

1. Giving website authors the chance to annotate address forms so that they can
   collect data in a format they need, enables browser vendors faciliate a
   better autofill experience.

2. In our opinion the metrics above indicate that websites frequently ask for
   street names and house numbers. They choose to use these formats despite a
   lack of support by the autocomplete attribute, so we don’t expect that
   nudging website authors towards an address representation with
   `address-line1, 2, 3`, is likely to succeed (c/f
   https://github.com/whatwg/html/issues/4986#issuecomment-552055169).

3. We see that some websites try using autocomplete attributes for this use
   case. They typically choose `address-line1` for the street name and
   `address-line2` for the house number. The effect on Chrome was pretty random
   from a user’s perspective, depending on the address profile stored. We also
   see that website authors introduce inofficial/self-defined attributes like
   `house-number` and pair them with official attributes like `given-name` and
   `family-name`.

4. Even if browsers decide not to support street names and house numbers, adding
   them to the spec could be a win in the sense that forms are not filled
   instead of incorrectly filled.

## Goals and principles

### Follow the needs of websites

> **Context:**
>
> A company told us that their shipping label printer prescribes them the format
> for addresses. They don’t want to be in the business of tokenizing address
> strings.
>
> Our analysis tells us that the local customs and needs decide how websites
> structure their address forms. Not the lowest common denominator proposed by
> the HTML spec. A beautiful and pure standard is useless if it does not get
> traction.

> **Proposal:**
>
> Where possible and reasonable, we follow the customs of real-world websites we
> can observe today. We don't try to coerce websites towards a lowest common
> global denominator. "Reasonable" means that we aim at supporting trends in a
> country, not every snow flake website.

> **Status:**
>
> Proposed but not discussed. ([Issue
> #5](https://github.com/battre/autocomplete-attribute-explainer/issues/5))

### Enable per-country specific extensions

> **Context:**
>
> For example, Spanish and Hungarian address forms (sometimes) separate the type
> of a street from the name of the street. Japanese websites ask for a phonetic
> spelling of a name. Some countries employ landmarks.

> **Proposal:**
>
> This is a corollary of "Follow the needs of websites": We want to support
> field types that are popular (and required) in a small set of countries
> (possibly a single country) and don't exist in other countries.
>
> We need to tell site authors which attributes are supported for different
> countries.
>
> In the beginning we will focus on names and addresses. In the future, new
> field types like tax payer IDs, new forms of payments, etc. can be in scope.

> **Status:**
>
> Proposed but not discussed. ([Issue
> #6](https://github.com/battre/autocomplete-attribute-explainer/issues/6))

### Tell developers how to interpret concepts in different languages
> **Context:**
>
> For example in Germany you don’t write a state on an envelope to get a letter
> shipped. Yet, the concept of a state exists as a political entity. It's
> unclear from the autocomplete spec, whether this makes the city an
> `address-level1` field or an `address-level2` field. We should remove this
> ambiguity.

> **Proposal:**
>
> Many websites are optimized for local markets. We want to give these websites
> (and browsers that support autofill on these websites) concrete hints about
> the semantics of fields.

> **Status:**
>
> Proposed but not discussed. ([Issue
> #7](https://github.com/battre/autocomplete-attribute-explainer/issues/7))


### Support compound types of different granularities

> **Context:**
>
> The some websites in a country may ask users to break their address into
> atomic tokens (e.g. by asking for a floor number and apartment number in
> separate fields) while other websites in the same country ask the user may ask
> the user to provide compound data (e.g. by asking to enter the floor number
> and apartment number in a single field).

> **Proposal:**
>
> We will analyze address forms in different countries and enable filling the
> combinations of data we observe on a non-trivial set of sites (we may ignore
> rare slowflakes).
>
> It is currently unclear whether it would be better to introduce a new field
> type like `"floor_number_and_apartment"` or whether to introduce a union of
> multiple types like `"floor_number + apartment"`.
>
> Websites must only use combinations of fields that have been blessed by the
> spec so that browsers can get instructions on how to assemble the data for a
> field with multiple atomic types.

> **Status:**
>
> Proposed but not discussed. ([Issue
> #8](https://github.com/battre/autocomplete-attribute-explainer/issues/8))

### Roll out iteratively

> **Context:**
>
> Understanding address formats from $N$ countries is a herculean task that is
> easy to get wrong because of cultural biases. Past examples of such incorrect
> assumptions in Google Chrome included "a last name consists of a single word",
> "every country uses postal codes" or "there is no entity between a state and a
> city".
>
> We have seen cases where websites adapted to the (incorrect) browser behavior
> rather than the spec.

> **Proposal:**
>
> We should roll this out country by country with a reasonable high confidence
> that we have modeled a country correctly, rather than aiming for an immediate
> global launch.

> **Status:**
>
> Proposed but not discussed.

## Proposed strategy

### Introducing a new attribute

At a very high-level we propose to introduce a *new attribute* `autofill`, which
is inteded to replace the current `autocomplete` attribute over time.

#### Advantages

Introducing a new attribute comes with a couple of advantages, in particular it
means that we don't need to be backwards compatible.

* **Browser behavior influenced interpretation of the spec:** Google Chrome (and
  possibly) other browsers did not implement the autocomplete spec correctly. It
  implemented a hard-coded expectation that an `address-level1` corresponds to a
  state and an `address-level2` corresponds to a city. This is an incorrect
  assumption. In Mexico for example, the state ("Estado") is subdivided into
  municipalities ("Municipio") or delegaciones in case of Mexico. The
  municipalities are subdivided into cities ("Ciudad"). A correct mapping
  according to the autocomplete spec would be:
  * Estado = `address-level1`
  * Municipio = `address-level2`
  * Ciudad = `address-level3`

  However, because browsers did not support the concept of a Municipio and hard
  coded a city as `address-level2`, many websites today have annotations like
  the following:
  ```
  <input type="text" id="estado" autocomplete="address-level1">
  <input type="text" id="municipio">
  <input type="text" id="ciudad" autocomplete="address-level2">
  ```
  If browsers started interpreting `autocomplete="address-level2"` differently,
  they would break these websites.

* **No backwards compatible syntax / Support unions of field types:** We have
  observed that websites allow users to enter multiple tokens of an address into
  a single field. For example in Argentina we observe websites that have
  separate fields for the floor ("Piso") and apartment ("Departamento") but we
  also observed websites that accepted both entries in a single field ("Piso y
  Departamento"). Another pattern we observed is that websites asked for
  "Recipient name or Company".

  A new `autofill` attribute allows us to be more flexible with the syntax and
  would not throw off browsers that don't implement the new logic.

* **Blank slate for autocomplete="off"**: The autocomplete spec contains the
  `off` keyword which is set on many websites where one would not expect it.
  Some browsers (e.g. Google Chrome) decided to ignore `autocomplete="off"`
  because the autofill feature would feel broken from a user's specective. There
  are probably a series of reasons to block autocomplete:
  * The website never requests autofill because it is unlikely that the user
    enters their personal information. E.g. if the user is working in a call
    center and enters customer's data.
  * The website would be happy to have an address filled but also has an
    autocomplete feature which would collide with an autocomplete feature by the
    browser.
  * The website observed that browsers' autocomplete performed poorly (e.g.
    because the website asked for a house number which was not supported by
    most browsers).

  A new autocomplete attribute enables a more fine grained handling by browsers.
  Especially for the second case, the browser could offer treatment that does
  not collide with the UI of the website and would not inherit the legacy of the
  third case.

#### Disadvantages

* Introducing more APIs increases complexity.

#### Conclusion

> **Proposal:**
>
> We propose a new attribute called `autofill` that takes precedence over
> `autocomplete` if both are specified.
>
> The `autofill` attribute should provide a superset of the features of
> `autocompelte` so that websites which choose to use unstructured addresses
> get support for this.

> **Status:**
>
> Proposed but not discussed.

### Lowest common denominator vs. framework with country specific profiles

The current `autocomplete` spec tried to nudge all websites to use a lowest
common denominator for address formats. It suggested using a single full name
field intead of using given and family name fields. It asked for unstructured
address lines instead of asking for a house number and street name.

In theory this is a great strategy.

In practice it turns out that this approach suffered from two major challenges:
* Many websites preferred to follow local customs or requirements of shipping
  companies and did not ask for unstructured information but implemented the
  form structure they desired and thereby did not support the autocomplete spec.
* Concepts like `address-levelX` were not very clear and we are not aware
  of any browsers that support `address-level3` or higher.

We propose that the `autofill` attribute follows a similar strategy as
ISO 19160:

A **core model** offers a modelling framework for addresses which is
complemented by **country-specific profiles** which explain how to apply the
model for specific countries.

In practice, this means that the core model can contain concepts such as
`address-level1`, `address-level2`, `address-level3` and the country-specific
profile assigns meanings to these concepts. For example, in Mexico it would
specify that `address-level1` corresponds to "Estado", `address-level2`
corresponds to "Delegación o Municipio" and `address-level3` to "Ciudad".
Besides assigning meaning to fields, this would also allow-list field types for
countries. In many countries like the USA or Germany, an `address-level3` would
be undefined. While it's conceivable to consider neighborhoods or villages as
`address-level3` in the US or Germany, it is very uncommon that websites would
ask for such fields.

#### Advantages

* For websites that target specific markets, developers can look up the country
  profiles and get very specific information for how to build address forms for
  their markets. For example, Germany has states but they are typically not used
  on address forms. It is unclear whether that puts a city to `address-level1`
  or `address-level2`.
* Having country specific profiles allows adding complexity that is essential in
  some countries but hide it for other countries. For example, Japan requires
  phonetic names, which don't exist in most countries. Website developers for
  other countries would not need to be bothered about such concepts.
* The county-specific profile allows combining atomic data types into compound
  types. For example a street name and house number are combined as `"${house
  number} ${street name}"` in the US while German addresses use `"${street name}
  ${house number}"`. Some countries may have muliple valid ways of expressing a
  set of tokens.

#### Disadvantages

* It becomes much harder to build an address form that works for users from all
  countries. If that's a priority websites should use unstructured

The obvious question is why we don't just reuse ISO 19160. We should

#### Conclusion

> **Proposal:**
>
> We will produce a higher-level architecture that supports generic concepts
> and country specific profiles.
>
> The country specific profiles should be feature compatible with the current
> autofill spec (i.e. for every country we should have a meaningful definition
> of a street-address or an address-level1). The country specific profiles may
> extend the current autofill spec by new field types (e.g. street names, house
> numbers, etc.).
>
> To prevent problems in the future like the omission of "municipio" between
> `address-level1` and `address-level2` in Mexico, the `autofill` must only be
> used for countries that have a profile.
>
> The profile to use for an address form can be inferred from a country
> `<select>` element or guessed via browser heuristics.

> **Status:**
>
> Proposed but not discussed.

[autocomplete attribute]: (https://html.spec.whatwg.org/multipage/form-control-infrastructure.html#autofill)