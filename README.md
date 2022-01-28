# Proposal for extending the autocomplete attribute

**Written**: 2022-01-28, **Updated**: n/a

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

## Metrics

In order to assess the frequency of structured address information and also to
add heuristic support for fields that ask for street names and house numbers, 
Chrome has added simple heuristics for detecting these field types.

Chrome applies the following regular expressions to human-visible labels
(`placeholder` attribute, `label` tags, ..., all the way to what Chrome believes
to be the human-visible label of an input element based on the DOM structure)
and names (`name` or `id` attributes) of input elements. Only if both regular
expressions match a label or name, it reports these matchs. This means that it
is not sufficient to have an `<input name="number">` in isolation without
something that matches a street name regular expression.

```c++
const char16_t kStreetNameRe[] =
    u"stra(ss|ß)e"              // de
    u"|street"                  // en
    u"|улица|название.?улицы"   // ru
    u"|rua|avenida"             // pt-PT, pt-BR
    u"|((?<!do |de )endereço)"  // pt-BR
    u"|calle";                  // es-MX
const char16_t kHouseNumberRe[] =
    u"(house.?|street.?|^)number"              // en
    u"|(haus|^)(nummer|nr\\.?)"                // de
    u"|^\\*?.?número(.?\\*?$| da residência)"  // pt-BR, pt-PT
    u"|дом|номер.?дома"                        // ru
    u"|exterior";                              // es-MX
```

On top of that we apply some crowdsourcing.

The following statistics represent the ratios of *number of detected street name
fields* over *number of detected city fields* of *submitted forms*. We have
chosen these values to count the number of form submissions rather than the
number of domains for assessing impact of this proposal. We have chosen the
number of detected city fields as a baseline of how many address forms users
submitted.

| Country                 | Ratio |
| :---------------------- | ----: |
| Germany                 | 33.5% |
| Brazil                  | 27.9% |
| Mexico                  | 16.2% |
| Russia                  | 15.3% |
| Argentina               | 20.8% |
| Belgium                 | 14.3% |
| Poland                  | 11.1% |
| Netherlands             |  9.5% |
| Ukraine                 |  9.4% |
| Chile                   |  6.8% |
| Spain                   |  4.3% |
| Great Britain           |  1.5% |
| France                  |  1.1% |
| USA                     |  0.2% |
| Japan                   |    0% |
| Across the entire world |  3.9% |

The ratios of *house number* to *city* fields are typically in a similar range.
A notable exception is Brazil, where many address forms ask for a *zip code* and
a *house number* because the *street name* and other information can be derived
from the *zip code*. The *house number* to *city* ratio in Brazil is 47.6%.

> **Note:** These metrics are probably lower bounds:
> 
> We have selected only a few candidate countries for which we have created
> regular expressions so far. E.g. for Poland we would only detect a *street 
> name* / *house number* if the developer chose the English terms “street” and
> “house number” as the `name` or `id` attribute of an `<input>` element. We 
> would not detect those fields if the developer chose the merely the human
> readable Polish labels “ulica” / “numer domu” in combination with generic
> `name` or `id` attributes such as `field1`.
> 
> We have divided the number of submitted forms with street name fields by the
> number of submitted forms with city fields. There are many forms that ask for
> your city, but not for your full address (e.g. when selecting a nearby store).
> If we were to consider only proper shipping address forms, the computed ratios
> might be higher.

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

## Proposed syntax

We don’t have strong feelings regarding the syntax. We believe that 
`address-line1-street-name` (see comment
[here](https://github.com/whatwg/html/issues/4986#issuecomment-542088516))
might cause problems for other field types (e.g. apartment numbers) where there
is no clear assignment to specific address line numbers.

For this reason, we have a slight preference for “street-name” and 
“apartment-number”. We went one step further to propose adding even more field
types than "street name" and "house number". Here is the proposal:

<table>
<tr style="vertical-align: top">
  <th colspan=3>Field name</th>
  <th>Meaning</th>
  <th>Canonical Format</th>
  <th>Canonical Format Example</th>
  <th>Control group</th>
</tr>
<tr style="vertical-align: top">
  <td colspan=3>"street-address"</td>
  <td>Street address (multiple lines, newlines preserved)</td>
  <td>Free-form text</td>
  <td>32 Vassar Street<br />MIT Room 32-G524</td>
  <td>Multiline
</tr>
<tr style="vertical-align: top">
  <td></td>
  <td colspan=2>"address-line1"</td>
  <td rowspan=3>Street address (one line per field)</td>
  <td>Free-form text, no newlines</td>
  <td>32 Vassar Street</td>
  <td>Text</td>
</tr>
<tr style="vertical-align: top">
  <td></td>
  <td colspan=2>"address-line2"</td>
  <td>Free-form text, no newlines</td>
  <td>MIT Room 32-G524</td>
  <td>Text</td>
</tr>
<tr style="vertical-align: top">
  <td></td>
  <td colspan=2>"address-line3"</td>
  <td>Free-form text, no newlines</td>
  <td></td>
  <td>Text</td>
</tr>
<tr style="vertical-align: top">
  <td></td>
  <td colspan=2>"street-name"</td>
  <td>Name of a street<br /><br />(not to be combined with address-lineX)</td>
  <td>Free-form text, no newlines</td>
  <td>Vassar Street</td>
  <td>Text</td>
</tr>
<tr style="vertical-align: top">
  <td></td>
  <td colspan=2>"house-number"</td>
  <td>Predominantly numeric identifier for a house (where applicable)<br /><br />(not to be combined with address-lineX)</td>
  <td>Free-form text, no newlines</td>
  <td>32, could contain sub-units: 32-100, 32-a</td>
  <td>Text</td>
</tr>
<tr style="vertical-align: top">
  <td></td>
  <td colspan=2>"premise" (or “building-name”?)</td>
  <td>Building name (where applicable<br /><br />(not to be combined with address-lineX)</td>
  <td>Free-form text, no newlines</td>
  <td>32</td>
  <td>Text</td>
</tr>
<tr style="vertical-align: top">
  <td></td>
  <td colspan=2>"staircase"</td>
  <td>Name of a staircase<br /><br />(not to be combined with address-lineX)</td>
  <td>Free-form text, no newlines</td>
  <td>1</td>
  <td>Text</td>
</tr>
<tr style="vertical-align: top">
  <td></td>
  <td colspan=2>"sub-premise" (or “sub-unit”?)</td>
  <td>Identifier of sub-premise (e.g. apartment, room, ...) inside the building.<br />If a sub-premise has only a floor-number and no apartment (or vice versa), this would default to the non-empty value.<br /><br />(not to be combined with address-lineX)</td>
  <td>Free-form text, no newlines</td>
  <td>G524</td>
  <td>Text</td>
</tr>
<tr style="vertical-align: top">
  <td></td>
  <td></td>
  <td colspan=1>"floor-number"</td>
  <td>Floor number<br /><br />(not to be combined with address-lineX)</td>
  <td>Free-form text, no newlines</td>
  <td>G, often times numeric: 4</td>
  <td>Text</td>
</tr>
<tr style="vertical-align: top">
  <td></td>
  <td></td>
  <td colspan=1>"apartment"</td>
  <td>Apartment, room or door number<br /><br />(not to be combined with address-lineX)</td>
  <td>Free-form text, no newlines</td>
  <td>524</td>
  <td>Text</td>
</tr>
<tr style="vertical-align: top">
  <td></td>
  <td></td>
  <td colspan=1>"delivery-instructions"</td>
  <td>Delivery instructions<br /><br />(not to be combined with address-lineX)</td>
  <td>Free-form text</td>
  <td>Use gate code: 3315</td>
  <td>Text</td>
</tr>
</table>

*We would suggest adding something like the following to elaborate:*

> ### Structured and unstructured street addresses.
> 
> A “street-address” can be broken down into multiple address lines
> (“address-lineX”) or **alternatively** into more structured information
> (“street-name”, “house-number”, ..., “delivery-instructions”). Because there
> is no agreed-upon distribution of the various structured information into
> address-lineX fields, a website should not mix these two types of fields. The
> result would be unpredictable.

> **TODO:**
>
> Open question: Should there be some overflow field? Should we assume that a
> merchant knows which pieces of information to ask for a reliable delivery? Or
> should there be an overflow field. E.g. if the user specifies a staircase but
> the website does not ask for it, we could add "Staircase: X" to that overflow
> field. Or we could append/prepend such information to the delivery
> instructions.

## Implementation by browsers

As indicated above, today the behavior by browsers is pretty much random
depending on how website authors choose to interpret the meanings of
`address-line1` and `address-line2`. The number of websites asking for structured
information indicates that a lack of support by the autocomplete attribute did
not prevent websites from using this representation.

If we extend the specification in the proposed way, browser vendors can pursue
at least the following strategies:

* No filling of “street-name” and “house-number” (or other not-supported field
  types)
* Wrong - but consistently wrong - filling: E.g. fill “address-line1” into
  “street-name” and nothing into “house-number” (other not-supported field types
  could remain blank).
* Ask the user for a structured representation and an unstructured
  representation (i.e., address-line1, 2, 3). Learn “street-name”,
  “apartment-number” and other structured data from “street-address”: If the
  user stores a “street-address” in the browser and visits a website with
  structured fields for the first time, nothing would be filled. The user would
  type their information and the browser would see that the tokens of the
  structured address can be found in the unstructured address and associate the
  structured representation with the unstructured address. On the next filling,
  the structured information would be available. Chrome has built some slightly
  complex logic that tries to map between a street-address and more structured
  information.
  (https://source.chromium.org/chromium/chromium/src/+/main:components/autofill/core/browser/data_model/autofill_structured_address.h)
* Ask the user to enter a structured and an anstructured representation of their
  address.

Chrome would pursue the last two strategies.

## Follow-up work

We may want to introduce similar logic to names because it is pretty common in
Hispanic/Latinx communities to have two last names. We see that websites ask for
"primer apellido" and "segundo apellido" or "apellido paterno" and "apellido
materno" in separate fields.

[autocomplete attribute]: (https://html.spec.whatwg.org/multipage/form-control-infrastructure.html#autofill)