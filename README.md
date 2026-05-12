# Bitumen Laboratory

ERPNext/Frappe app for Bitumen factory laboratory truck tests.

The app links incoming trucks to Weight Bridge Ticket records, evaluates Flash
Point and Viscosity against configurable limits, and records whether a truck
passed or was rejected before it is routed to a pool.

## App

- App name: `bitumen_laboratory`
- Module: `Bitumen Laboratory`
- Requires: ERPNext and the custom `weight_bridge` app

## Main DocTypes

- `Laboratory Truck Test`
- `Laboratory Settings`

## Weight Bridge Integration

On install, the app adds read-only laboratory fields to `Weight Bridge Ticket`:

- `Laboratory Status`
- `Laboratory Test`
- `Laboratory Pool`

Rejected lab tests also add/use the `Rejected` option in the Weight Bridge
Ticket status field so rejected trucks can leave without disturbing the normal
second-weight flow for passed trucks.

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
