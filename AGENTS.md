# Repository instructions

Read README.md before changing build or release behavior. Use the package.json
commands: `yarn test`, `yarn validate`, `yarn plan`, `yarn build:wheel` and
`yarn publish`. No JavaScript dependencies are needed; the scripts use Python.
Never move a source pin, change a wheel filename without updating its metadata,
overwrite a published asset, or mark a GPU runtime test as passed on a CPU runner.
Keep each package and target independently selectable and fingerprinted.
