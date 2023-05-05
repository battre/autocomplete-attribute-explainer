# Proposal for extending the autocomplete attribute

**Written**: 2022-01-28, **Updated**: 2023-03-13

## tl;dr

This is a proposal to extend the [autocomplete attribute] in HTML to match the
structures of address forms we can observe on today's web.

A companion feature request exists at https://github.com/whatwg/html/issues/4986

Today's [autocomplete attribute] provides an opinionated list of field names
that prescribe how to structure an address form (and other data types which are
out of scope of this proposal) in order to be compatible with autofilling by the
user agent. In particular it assumes a structure containing elements like
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

This document proposes an alternative way to annotate form fields with their
expected types of address information:
* We propose introducing an `autofill` attribute which takes precedence over
  `autocomplete` for browsers that support it.
* `autofill` supports the concepts of `autocomplete` but extends them.
* `autofill` does not force websites to use the unstructured address format of
  `autocomplete` (e.g. relying on address-lineX fields). It allows websites to
  get browser-based autofill on their their forms which follow local customs or
  requirements of local shipping companies. This may mean requesting fine
  grained data types like a street name, house number, floor number, etc.
* The `autofill` attribute is based on the idea of having a framework to
  describe addresses in general. This framework is adapted to the needs of
  different countries via country profiles (similarly to ISO 19160). This allows
  us to support field types that are very common in some countries but
  non-existent as individual fields in others.
* The country profiles make it much easier for websites to associate meaning to
  abstract terms (e.g. answering what's an address-level2) and fix incorrect
  interpretations of the spec which have become the defacto standard on the web.

## Motivation

Our [Country
Analysis](https://battre.github.io/autocomplete-attribute-explainer/index.html)
looked at 26 different countries and identified that only in a small minority of
countries the commonly used structures to express address forms are well
supported by today's `autocomplete` attribute.

Our arguments for adding the new autocomplete types (“Field names” in the HTML
Spec) are:

1. Giving website authors the chance to annotate address forms so that they can
   collect data in a format they need and enable browser vendors to facilitate a
   better autofill experience for such forms.

2. The metrics cited above indicate to us that in multiple countries, websites
   predominately ask for separate street name and house numbers rather than
   street addresses or address lines as they are defined by the autocomplete
   attribute. They choose to use these formats despite a lack of support by the
   autocomplete attribute, so we don’t expect that nudging website authors
   towards an address representation with `address-line1, 2, 3`, is likely to
   succeed (c/f
   https://github.com/whatwg/html/issues/4986#issuecomment-552055169).

3. We see that some websites try to borrow the existing autocomplete attributes
   for this use case. They typically choose `address-line1` for the street name
   and `address-line2` for the house number. For a properly stored address, both
   the street name and the house number will be in `address-line1` in most
   countries. Therefore the information will be filled incorrectly and the filling
   behavior is pretty random from a user’s perspective, depending on the
   address profile stored. We also see that website authors introduce
   unofficial/self-defined attributes like `house-number` and pair them with
   official attributes like `given-name` and `family-name`.

## Goals and principles

### Follow the needs of websites

> **Context:**
>
> Our analysis tells us that the local customs and needs (e.g. for integrations
> into 3P solutions like shipping companies) decide how websites structure their
> address forms. Not the lowest common denominator proposed by the HTML spec. A
> beautiful and pure standard is useless if it does not get traction.
>
> A company told us that their shipping label printer prescribes them the format
> for addresses. They don’t want to be in the business of tokenizing address
> strings.
>
> We should meet websites where it's convenient for them, not where it's
> convenient for browsers.

> **Proposal:**
>
> Where possible and reasonable, we follow the customs of real-world websites we
> can observe today. We don't try to coerce websites towards the lowest common
> global denominator. "Reasonable" means that we aim at supporting trends in a
> country, not every snowflake website.

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
> This is a corollary of "Follow the needs of websites": We also want to support
> field types that are popular (and required) in a small set of countries
> (possibly a single country) and don't exist in other countries.
>
> We need to tell site authors which attributes are supported for different
> countries.
>
> In the beginning we will focus on names and addresses. In the future, new
> field types like taxpayer IDs, new types of payments, etc. can be in scope.

> **Status:**
>
> Proposed but not discussed. ([Issue
> #6](https://github.com/battre/autocomplete-attribute-explainer/issues/6))

### Tell developers how to interpret concepts in different countries

> **Context:**
>
> For example in Germany you don’t write a state on an envelope to get a letter
> shipped. Yet, the concept of a state exists as a political entity. It's
> unclear from the autocomplete spec whether this makes the city an
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
> Depending on the country, some websites may ask users to break their address
> into atomic tokens (e.g. by asking for the floor and apartment number in
> separate fields) while other websites in the same country ask the user to
> provide compound data (e.g. by asking to enter the floor number and apartment
> number in a single field).

> **Proposal:**
>
> We will analyze address forms in different countries and enable filling the
> combinations of data we observe on a non-trivial set of sites (we may ignore
> rare snowflakes).
>
> It is currently unclear whether it would be better to introduce a new field
> type like `"floor_number_and_apartment"` or whether to introduce a union of
> multiple types like `"floor_number + apartment"`.
>
> Websites must only use combinations of fields that have been blessed by the
> spec either way. This is necessary so that browsers can get instructions from
> the country profiles which are being generated as part of this spec and
> explain how to assemble the data for a field with multiple atomic types.

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
>
> We have recently tried to follow the principles outlined in the document and
> created address hierarchies for the US, Brazil, Mexico and India. It was
> very aparent that a lot of country knowledge is necessary to model addresses
> for a country properly. Even with people who grew up in a country it was often
> not aparent whether there was a single, clear best solution.

> **Concerns:**
>
> Could we find a way to roll this out by level of detail (e.g. add support for
> street names and house numbers)? We don't know... Such a strategy comes with a
> risk of manifesting incorrect assumptions that are hard to revert.

> **Proposal:**
>
> We should model a small number of diverse countries upfront and then roll this
> out country by country with a reasonable high confidence that we have modeled
> the selected countries correctly, rather than aiming for an immediate global
> launch.

> **Status:**
>
> Proposed but not discussed. ([Issue
> #9](https://github.com/battre/autocomplete-attribute-explainer/issues/9))

## Proposed strategy

### Introducing a new attribute

At a very high-level we propose to introduce a *new attribute* `autofill`, which
is intended to replace the current `autocomplete` attribute over time.

#### Advantages

Introducing a new attribute comes with a couple of advantages, in particular it
means that we don't need to be backwards compatible.

* **Browser behavior influenced interpretation of the spec:** Google Chrome (and
  possibly other browsers) did not implement the autocomplete spec correctly.
  Chrome implemented a hard-coded expectation that an `address-level1`
  corresponds to a state and an `address-level2` corresponds to a city. This is
  an incorrect assumption. In Mexico for example, the state ("Estado") is
  subdivided into municipalities ("Municipio"), or in case of Mexico City into
  boroughs ("Delegaciones"). The municipalities are again subdivided into cities
  ("Ciudad"). A correct mapping according to the autocomplete spec would be:
  * Estado = `address-level1`
  * Municipio = `address-level2`
  * Ciudad = `address-level3`

  However, because browsers did not support the concept of a Municipio and hard
  coded a city as `address-level2`, we have seen websites today have annotations
  like the following:
  ```
  <input type="text" id="estado" autocomplete="address-level1">
  <input type="text" id="municipio">
  <input type="text" id="ciudad" autocomplete="address-level2">
  ```
  If browsers started interpreting `autocomplete="address-level2"` differently,
  they would break these websites.

* **No backwards compatible syntax / support unions of field types:** We have
  observed that websites allow users to enter multiple tokens of an address into
  a single field. For example, in Argentina we observe websites that have
  separate fields for the floor ("Piso") and apartment ("Departamento") but we
  also observe websites that accept both entries in a single field ("Piso y
  Departamento"). Another pattern we observed is that websites asked for
  "Recipient name or Company".

  A new `autofill` attribute allows us to be more flexible with the syntax and
  would not throw off browsers that don't implement the new logic.

* (out of scope for this proposal but possibly relevant:) **Blank slate for
  autocomplete="off"**: The autocomplete spec contains the `off` keyword which
  is set on many websites where one would not expect it. Some browsers (e.g.
  Google Chrome) decided to ignore `autocomplete="off"` because the autofill
  feature would feel broken from a user's perspective. There are probably a
  series of reasons to block autocomplete:
  * The website never requests autofill because it is unlikely that the user
    enters their personal information. E.g. if the user is working in a call
    center and enters customer's data.
  * The website would be happy to have an address filled but also has an
    autocomplete feature on its own which would have a colliding UI with the
    autocomplete feature by the browser.
  * The website observed that browsers' autocomplete performed poorly (e.g.
    because the website asked for a house number which was not supported by
    most browsers).

  A new autocomplete attribute enables a more fine grained handling by browsers.
  Especially for the second case, the browser could offer treatment that does
  not collide with the UI of the website and would not inherit the legacy of the
  third case.

#### Disadvantages

* Introducing more APIs increases complexity by growing the surface of the HTML
  standard that developers may need to be aware of.

#### Conclusion

> **Proposal:**
>
> We propose a new attribute called `autofill` that takes precedence over
> `autocomplete` if both are specified.
>
> The `autofill` attribute should provide a superset of the features of
> `autocomplete` so that websites which choose to use unstructured addresses
> get support for this.

> **Status:**
>
> Proposed but not discussed. ([Issue
> #10](https://github.com/battre/autocomplete-attribute-explainer/issues/10))

### Lowest common denominator vs. framework with country-specific profiles

The current `autocomplete` spec tries to nudge all websites to use the lowest
common denominator for address formats. It suggested using a single full name
field instead of using given and family name fields. It asked for unstructured
address lines instead of asking for a house number and street name.

In practice it turns out that this approach suffers from two major challenges:
* Many websites prefer to follow local customs or requirements of shipping
  companies and do not ask for unstructured information but implement the
  form structure they desire and thereby do not fully support the autocomplete
  spec.
* Concepts like `address-levelX` are not very clear and we are not aware
  of any browsers that support `address-level3` or higher.

We propose that the `autofill` attribute follows a similar strategy as
[ISO 19160](https://www.iso.org/standard/61710.html):

A **core model** offers a framework for describing addresses which is
complemented by **country-specific profiles**. Those explain how to apply and
adapt the framework for specific countries.

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

The obvious question is why we don't just reuse ISO 19160. ISO 19160 offers a
lot of details but also a high degree of complexity, which exceeds the address
forms we see on the internet. Many of the concepts defined in the standard are
not used in any of the country profiles. As such, it should be possible to
provide something simpler but sufficiently powerful.

To ensure that websites which target an international audience, we will define
a generic profile similar to today's `autocomplete` attribute (name,
street address, address-levels, postal code) and ensure that any country
profile as well as today's `autocomplete` attribute can be mapped to it. This
generic profile won't support the new data types like streetnames and house
house numbers.

#### Advantages

* For websites that target specific markets, developers can look up the country
  profiles and get very specific information for how to build address forms for
  their markets. For example, Germany has states but they are typically not used
  on address forms. It is unclear whether that puts a city to `address-level1`
  or `address-level2`.
* Having country-specific profiles allows adding complexity that is essential in
  some countries but hides it for other countries. For example, Japan requires
  phonetic names, which don't exist in most countries. Website developers for
  other countries would not need to be bothered about such concepts.
* The county-specific profile allows combining atomic data types into compound
  types. For example a street name and house number are combined as `"${house
  number} ${street name}"` in the US while German addresses use `"${street name}
  ${house number}"`. Some countries may have multiple valid ways of expressing a
  set of tokens.

#### Conclusion

> **Proposal:**
>
> We will produce a higher-level architecture that supports generic concepts
> and country-specific profiles.
>
> The country-specific profiles should be feature compatible with the current
> autocomplete spec (i.e. for every country we should have a meaningful
> definition of a street-address or an address-level1). The country-specific
> profiles may extend the current autocomplete spec by new field types (e.g.
> street names, house numbers, etc.).
>
> To prevent problems in the future like the omission of "municipio" between
> `address-level1` and `address-level2` in Mexico, the `autofill` attribute must
> only be used for countries that have a researched and well defined profile.
>
> **Status:**
>
> Proposed but not discussed. ([Issue
> #11](https://github.com/battre/autocomplete-attribute-explainer/issues/11))

### Using country profiles at form filling and submission time

At form *submission* time, knowing the country profile enables the browser to
* parse submitted information (e.g. "1600 42nd street" can be broken into a
  house number and street name by a parser that know that US addresses begin
  with a house number followed by a street name).
* tune the save prompts and address-edit UI (e.g. pick the right term for
  address-level1, like state, province, parish, emirate, island, ...; show the
  fields that are supported for a country and hide all others).
* validate data (e.g. do plausibility checks on phone numbers).

The browser can derive the country from a country `<select>` element. For
websites that only deliver/serve a single country, it would be great to declare
the address profile to use on the `<form>` tag.

At form *filling* time, the browser needs to work with the addresses it has
on file and the field types according to the autocomplete spec. If an address is
stored for country X and needs to be filled into an address form that requests
addresses for country Y, the filling will happen at best effort.

> **Status:**
>
> Proposed but not discussed. ([Issue
> #18](https://github.com/battre/autocomplete-attribute-explainer/issues/18))

### Modeling states and cities

The autocomplete spec relies on a single hierarchy (address-level1 to
address-level4) to model states and cities.

This comes with the challenge that the administrative areas may not overlap
with the information hierarchy needed for the postal system.

For example, Mexico is organized (ignoring Mexico City) into 32 states (estado).
These states are organized into municipalities (municipio). *Some* of those
(like [Tijuana](https://en.wikipedia.org/wiki/Tijuana_Municipality)) are
organized into boroughs (delegaciónes), while others are not. The municipalities
have cities (ciudad) that are broken into neighborhoods (colonia).

Germany comprises 16 federal states (Länder) and several of those are broken
into administrative districts (Regierungsbezirke). Neither of these are relevant
for postal addresses, but sometimes the states are requested on webforms.

We propose to introduce an admin-area1, ..., admin-area4 hierarchy, which one
can think of as states and subdivisions, plus a locality1, ..., locality4
hierarchy, which one can think of as cities, neighborhoods/districts, ...

By splitting these two, we retain the freedom to introduce finer-level
granularities in either of the two hierarchies retrospectively. The problem of
omitting the `municipio` level in Chrome's address hierarchy could have been
fixed this way.

The [List of administrative divisions by
country](https://en.wikipedia.org/wiki/List_of_administrative_divisions_by_country)
by Wikipedia may help modeling the admin-areas.

#### Advantages

* Different states may have different levels of nesting. By splitting the
  admin-area from the locality, we introduce a constant reference point for
  cities, regardless of how many levels of depth a website requests on the
  admin-areas.
* We introduce a new concept (`admin-areaX` and `localityX`) which is different
  from the old `admin-levelX` and enables a fresh start for countries where the
  spec diverged from browser behavior (at least Chrome hard-coded admin-level2
  to cities and websites started to rely on that, which makes it hard to fix
  now).
* We could introduce a concept like `admin-area2+` which would fill
  `admin-area2` through `admin-area4` (e.g. comma separated), depending on how
  much information is available, but keep the city for a separate field.
* Websites could ask for a state and city via `admin-area1` and `locality1` and
  would get the data filled for US and Mexican addresses, where a correct
  implementation of the current autocomplete spec would require the website to
  ask for `address-level1` and `address-level2` for US addresses and
  `address-level1` and `address-level3` for Mexican addresses.

#### Disadvantages

* In some countries there may be no clear intuition where an admin-area ends and
  a locality starts.

#### Conclusion

> **Proposal:**
>
> We introduce two hierarchies:
> * `admin-area1`, `admin-area2`, `admin-area3`, `admin-area4`
> * `locality1`, `locality2`, `locality3`, `locality4`
>
> It's up for debate whether we should go with the more inclusive `admin-areaX`
> and `localityX` terms or whether whether we use the easier to understand but
> possibly wrong terms `state`, `sub-state`, `???`; `city`, `district`,
> `sub-district`. [A long time
> ago](https://raw.githubusercontent.com/whatwg/html/1eb194f229a6e481f313320a396b9da99b9f0706/source)
> the HTML spec had autocomplete values of `region` and `locality`. This was
> removed
> [here](https://github.com/whatwg/html/commit/8db70d1387817431f2a876d032ad77f2cd0a3f29);
> [discussion](https://www.w3.org/Bugs/Public/show_bug.cgi?id=25235).

> **Status:**
>
> Proposed but not discussed. ([Issue
> #12](https://github.com/battre/autocomplete-attribute-explainer/issues/12))

### Modeling addresses at a street level

A core aspect of this proposal is to introduce finer grained information for
address fields that are requested in many countries such as street name and
house number fields.

> **Proposal:**
>
> We propose to maintain the concept of a `street-address` and the
> `address-lineX` fields (we may want to introduce an `address-line4` for extra
> flexibility).
>
> On top of that we need to cater for the more structured use cases and propose
> the following new types (names TBD, the list of fields it not exhaustive):
>
> * `street-location` - This is what frequently goes into an `address-line1`.
>   The information that helps identifying a building in a street.
>   * `street` - The name of the street.
>     * `street-type` - Only a few countries split the name of the street from
>       the type of the street. Examples are Spain and Hungary. The type of a
>       street could be "Avenue" or "Road".
>     * `street-name`
>   * `building` - Fills either the `house-number` or `building-name`, or both,
>     depending on what's defined.
>     * `house-number` - The number assigned to a building in a street.
>     * `building-name` - Some countries reference buildings by a name (e.g.
>       India and sometimes Great Britain).
>
> An US website should use `street-location` or `street` and `building`: The
> distinction between `street-type` and `street-name` is uncommon and should not
> be brought infront of US users. If a Hungarian users tries to order somethingm
> their `street-type` and `street-name` would automatically be filled into a
> `street` field. For similar reasons, the website should just ask for a
> `building` and get what it expects. Only few countries, like the UK, which
> use a `house-number` *and* a `building-name` on address forms the distinction
> matters. Only in those countries would we support a `house-number` and
> `building-name`. This means, that browsers would not fill a building name or
> house number of addresses that were stored for other countries.

> **Status:**
>
> Proposed but not discussed. ([Issue
> #13](https://github.com/battre/autocomplete-attribute-explainer/issues/13))

### Modeling addresses at the building level

An address does not end at the building. We propose the following concepts to
route the delivery inside a building.

> **Proposal:**
>
> * `in-building-location` - This should be the primary way to request the
>   location within a building. This would be used for example if websites
>   specify "Apt, Unit, etc.". Websites that decide to ask for more fine-grained
>   information will use the fields below.
>   * `entrance` - Entrance of the building
>   * `floor` - Floor number of the apartment / unit.
>   * `staircase` - Staircase within the building.
>   * `unit` - e.g. "Apt 5". The fully spelled out apartment / unit, how it
>     should appear in `in-building-location`.
>     * `unit-type` - e.g. "Apt", "Room", "Store"
>     * `unit-name` - e.g. "5"
>
> Websites should not ask for an `in-building-location` and a `floor` in the
> same form.
>
> We introduced a split into `unit-type` and `unit-name` because some countries
> expect a 1 to 3 digit number for an apartment. But if a website of the same
> country asks for an unstructured street address we would still need to
> generate a string like "Apt. 5", so we would need to know the apartment type.
> Details need to be figured out in this space. This is only a first rough
> sketch.

> **Status:**
>
> Proposed but not discussed. ([Issue
> #14](https://github.com/battre/autocomplete-attribute-explainer/issues/14))

### Modeling further routing information

Several tokens don't fill well into the propose hierarchy:

> **Proposal:**
>
> * `address-overflow` - In several countries (e.g. Brazil or Germany) this
>   field complements the `street-location`. In these countries we often see the
>   fields (`street`, `house-number`, `address-overflow`). The field is
>   sometimes referred to as "additional information". It may be used to fill
>   information like an organization, a care-of, or serve as an overflow if the
>   previous field was not long enough.
> * `landmark` - This can be called a landmark or reference point.
> * `cross-streets` Several hispanic countries use a pair of cross-streets
>   (entre calles) to help locate a building. In theory this could be mapped to
>   a landmark, but we observe that websites asks for a landmark *and*
>   cross-streets and we observe, that some websites even split the
>   cross-streets into two fields.
> * `delivery-instructions` - Special instructions to a delivery person.
> * `care-of` - The name of the intermediary who is responsible for transferring
>   a piece of mail between the postal system and the final recipient.

> **Status:**
>
> Proposed but not discussed. ([Issue
> #15](https://github.com/battre/autocomplete-attribute-explainer/issues/15))

### Modeling country-specific hierarchies

Above we proposed the following hierarchy:

* `street-location`
  * `street`
    * `street-type`
    * `street-name`
  * `building`
    * `house-number`
    * `building-name`
* `in-building-location`
  * `entrance`
  * `floor`
  * `staircase`
  * `unit`
    * `unit-type`
    * `unit-name`

In some countries it is common to have one field for the street name and one for
the house number and apartment. In this case we should allow for flexibility
in hierarchies:

* `street-location`
  * `street`
  * `building-and-unit`
    * `building`
    * `unit`

#### Advantages

* By introducing `building-and-unit` as a first class citizen for countries
  in which it is common to combine the house number and unit into a single
  field, the internal data structure reflects reality. This makes it probably
  much easier to maintain a consistent state if browsers try to observe
  submitted address forms and use the data to update their stored addresses.

#### Disadvantages

* It is much harder to translate addresses from one country to another if the
  address hierarchy does not match.

> **Proposal:**
>
> We aim to have a single, predominant hierarchy for each country. This
> hierarchy does not need to be the same for every country.
>
> We may introduce country-specific nodes for this.

> **Status:**
>
> Proposed but not discussed. ([Issue
> #16](https://github.com/battre/autocomplete-attribute-explainer/issues/16))

### Compound field types

We may run into situations in which the proposed hierarchy is insufficient to
meet the needs of websites.

In India it is very common to combine the flat number (unit) and building name
in a single field, so the following address structure may be appropriate:

* `street-location`
  * `unit-and-building`
    * `unit`
    * `building`
  * `street`
  * `landmark`

Unfortunately, we observed the following combinations of fields:
* `unit-and-building` | `street` | `landmark` (3 fields)
* `unit-and-building` | `street` + `landmark` (2 fields)
* `unit-and-building` + `street` | `landmark` (2 fields)

There was no clearly predominant way to combine fields.

In countries like India it may be very difficult to learn the address from a
submitted form. We probably want to give websites the ability to request unions
of field types to be filled.

> **Proposal:**
>
> Allow websites to request combinations of field types (e.g.
> `unit-and-building` and `street`). Only allowlisted combinations will be
> supported. Browsers will get meta information for constructing such
> combinations. This meta information could express that
> `unit-and-building` and `street` are concatenated with a `,` in an
> `<input>` field and a `\n` in a `<textarea>`.
>
> The Chrome team has ideas for storing and updating alternative representations
> of address trees which we may share as design documents or an open source
> library if other browsers are interested in this.

> **Status:**
>
> Proposed but not discussed. ([Issue
> #17](https://github.com/battre/autocomplete-attribute-explainer/issues/17))

[autocomplete attribute]: (https://html.spec.whatwg.org/multipage/form-control-infrastructure.html#autofill)
