# Bitumen Laboratory

ERPNext/Frappe app for Bitumen factory laboratory truck tests.

The app links incoming trucks to Weight Bridge Ticket records, evaluates Flash
Point and Viscosity against configurable limits, and records whether a truck was
passed, rejected, or accepted into a pool by management exception.

## App

- App name: `bitumen_laboratory`
- Module: `Bitumen Laboratory`
- Requires: ERPNext and the custom `weight_bridge` app

## Main DocTypes

- `Laboratory Truck Test`
- `Laboratory Settings`

## Evaluation Modes

`Laboratory Settings` controls how lab results are decided:

- `Hybrid` is the default. It evaluates automatically only after Flash Point and
  Viscosity each have at least one configured limit. Until then, the test stays
  `Draft` and no pool is required.
- `Automatic` always uses configured limits and blocks submit until both tests
  have criteria.
- `Manual` lets the lab user choose `Passed`, `Rejected`, or `Accepted With
  Exception`.

Enable `Allow Failed Tests to be Accepted With Exception` when management may
approve a failed VR truck for a pool. These records require a pool and an
exception reason, and they do not mark the Weight Bridge Ticket as `Rejected`.

## Weight Bridge Integration

On install, the app adds read-only laboratory fields to `Weight Bridge Ticket`:

- `Laboratory Status`
- `Laboratory Test`
- `Laboratory Pool`

Rejected lab tests add/use the `Rejected` option in the Weight Bridge Ticket
status field so rejected trucks can leave. Passed tests and accepted exceptions
keep the truck in the normal second-weight flow.

## Install

Install `weight_bridge` first, then add this app to the bench:

```bash
bench get-app bitumen_laboratory https://github.com/Botanium/bitumen_laboratory
bench --site <site-name> install-app bitumen_laboratory
bench --site <site-name> migrate
bench build --app bitumen_laboratory
```

## Tests

Client-side form tests:

```bash
node --test tests/*.test.js
```

Frappe functional tests:

```bash
bench --site <site-name> run-tests --app bitumen_laboratory
```
