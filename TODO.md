# TO DOs

- [ ] Get some example files of real world AppProjects and ApplicationSets to use as templates.
- [ ] Make the platform.yaml file defaults to a relative file and path so the config does not have to be specified. The user should still be able to override it with a `--config` flag.
- [ ] Add more examples to the README.md file.
- [ ] Add some type of validation to ensure that the output paths specified in platform.yaml are valid and match the expected output paths in the OutputPaths model.
- [ ] Add some type of validation to make sure the generated files are valid YAML files and can be minimally parsed. The commad should be something like `platform-gen validate --path ./path/to/artifact.yaml`.
- [ ] Add support for implicitly handling git operation. Any generation command should automtically create git branches in the output paths with a common naming convention/pattern. Then, at the completion of the generation process, commit to that branch and push to the remote. PRs will be handled manually by the user.
- [ ] At the completion of the generation process, output a summary of what was generated, similar to how kubectl outputs a summary after applying manifests. This should include the file paths and types of artifacts generated along with the git status of the output directories.
- Provide an example of the ApplicationSet Git Generator
- [ ] Add more tests.
- [ ] Add some reasonable defaults to the platform.yaml file so a minimal config can be used.
- [ ] Add a Kong API Gateway Generator
- [ ] Add an External Secret Generator
- [ ] Add a Cert-Manager Certificate Generator
