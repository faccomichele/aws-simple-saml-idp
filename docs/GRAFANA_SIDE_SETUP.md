# SAML Provider

## General settings

Display name for this SAML 2.0 integration
`SAML - DEV`

Entity ID
`https://<mystack>.grafana.net/saml/metadata`

Allow signup
YES

Auto login
YES

Single logout
NO

Identity provider initiated login
YES

Relay state *
`unified-sso-portal `

Max issue delay
`90s`

Metadata valid duration
`48h`

## Sign requests

Sign requests
NO

## Finish configuring Grafana using IdP data

Metadata URL
`https://<apigw.deployment.url>/metadata`

## User mapping

### Assertion attributes mappings

Name attribute
`displayName`

Login attribute
`email`

Email attribute
`email`

Role attribute
`role`

External UID attribute
`email`

### Role mapping

Viewer
`viewer`

Editor
`editor`

Admin
`admin`

Skip organization role sync
YES
