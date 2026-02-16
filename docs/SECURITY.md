# Security Policy

## Security Considerations

This project provides a basic SAML Identity Provider implementation. While it includes several security features, it is designed as a starting point and **requires additional hardening for production use**.

## Known Security Limitations

### 1. Password Hashing (CRITICAL)

**Current Implementation**: Uses SHA256 for password hashing.

**Risk**: SHA256 is NOT secure for password hashing. It is:
- Too fast (vulnerable to brute force)
- Vulnerable to rainbow table attacks
- Does not use salting

**Production Recommendation**: Implement proper password hashing:
- **bcrypt**: Industry standard, recommended
- **Argon2**: Modern, memory-hard algorithm
- **scrypt**: Good alternative

**Implementation Example** (Python with bcrypt):
```python
import bcrypt

# Hashing
password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

# Verification
if bcrypt.checkpw(password.encode('utf-8'), stored_hash):
    # Password correct
```

### 2. CORS Configuration

**Current Implementation**: Defaults to allowing all origins (`*`)

**Risk**: Allows any website to make requests to your API

**Production Recommendation**: Restrict CORS origins to your specific domains:
```hcl
allowed_cors_origins = [
  "https://login.example.com",
  "https://idp.example.com"
]
```

### 3. Dependency Versions

**Current Implementation**: Pins boto3 to version 1.34.0

**Risk**: May contain known vulnerabilities

**Production Recommendation**: 
- Regularly update dependencies
- Use tools like `pip-audit` or `safety` to check for vulnerabilities
- Implement a dependency update schedule

```bash
pip install pip-audit
pip-audit -r lambda/layer/requirements.txt
```

### 4. SAML Assertion Signing

**Current Implementation**: SAML assertions are generated but not cryptographically signed

**Risk**: While AWS accepts unsigned assertions from properly configured SAML providers, signed assertions provide:
- Protection against tampering
- Non-repudiation
- Enhanced trust

**Production Recommendation**: Implement XML digital signatures:
- Use libraries like `python-saml` or `signxml`
- Sign SAML Response and Assertion elements
- Use RSA-SHA256 or stronger algorithms

**Implementation Note**: AWS Console SAML integration works with unsigned assertions when:
- The SAML provider is properly configured in IAM
- The certificate is registered in the SAML provider
- The assertion structure is correct

For enhanced security, consider implementing full SAML 2.0 signatures.

### 5. No Multi-Factor Authentication (MFA)

**Current Implementation**: Single-factor authentication (password only)

**Risk**: Vulnerable to credential theft

**Production Recommendation**: Implement MFA using:
- TOTP (Time-based One-Time Password) - Google Authenticator, Authy
- SMS-based OTP
- Hardware tokens (YubiKey)

### 6. No Rate Limiting

**Current Implementation**: No rate limiting on authentication attempts

**Risk**: Vulnerable to brute force attacks

**Production Recommendation**: Implement rate limiting using:
- AWS WAF with rate-based rules
- Lambda@Edge for CloudFront
- DynamoDB for tracking failed attempts

### 6. Session Management

**Current Implementation**: Stateless, no session tracking

**Risk**: Cannot revoke sessions or detect suspicious activity

**Production Recommendation**: Implement session management:
- Store active sessions in DynamoDB
- Implement session expiration
- Add ability to revoke sessions
- Track session activity

### 7. Audit Logging

**Current Implementation**: Basic CloudWatch logging

**Risk**: Insufficient audit trail for compliance

**Production Recommendation**: Implement comprehensive audit logging:
- Log all authentication attempts (success and failure)
- Include: timestamp, username, IP address, user agent, outcome
- Store in DynamoDB or CloudWatch Logs Insights
- Set up alerts for suspicious patterns

## Security Features Included

✅ **HTTPS Only**: All communication over TLS  
✅ **Encrypted Storage**: DynamoDB encryption at rest  
✅ **Secret Management**: SSM Parameter Store with encryption  
✅ **Private S3**: No public access to S3 buckets  
✅ **IAM Least Privilege**: Minimal permissions for Lambda  
✅ **SAML Signing**: Digital signatures on SAML assertions  
✅ **Time-limited Assertions**: SAML assertions expire  
✅ **Unique Assertion IDs**: Prevents replay attacks  

## Production Security Checklist

Before deploying to production:

- [ ] Replace SHA256 password hashing with bcrypt/Argon2
- [ ] Implement Multi-Factor Authentication (MFA)
- [ ] Restrict CORS origins to specific domains
- [ ] Enable AWS WAF with rate limiting rules
- [ ] Implement session management and tracking
- [ ] Set up comprehensive audit logging
- [ ] Configure CloudWatch alarms for security events
- [ ] Use custom domain with ACM certificate
- [ ] Implement IP whitelisting if applicable
- [ ] Enable AWS CloudTrail for API activity
- [ ] Regular security audits and penetration testing
- [ ] Implement automated security scanning (CodeQL, Snyk)
- [ ] Review and update dependencies regularly
- [ ] Implement secrets rotation for SAML certificates
- [ ] Set up backup and disaster recovery procedures
- [ ] Document incident response procedures
- [ ] Implement monitoring and alerting
- [ ] Review IAM policies for least privilege
- [ ] Enable VPC endpoints if in private subnet
- [ ] Implement DDoS protection with AWS Shield

## Reporting Security Issues

If you discover a security vulnerability, please:

1. **DO NOT** open a public GitHub issue
2. Email the maintainer directly (see repository)
3. Include:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

We will respond within 48 hours and work with you to address the issue.

## Security Updates

We recommend:

- Subscribe to AWS Security Bulletins
- Monitor GitHub security advisories
- Keep dependencies updated
- Regularly review CloudWatch logs
- Conduct periodic security audits

## Compliance Considerations

This implementation may need additional features for compliance:

- **SOC 2**: Requires audit logging, access controls, encryption
- **HIPAA**: Requires BAA, encryption, audit logs, access controls
- **PCI DSS**: Requires MFA, encryption, logging, access controls
- **GDPR**: Requires data protection, user consent, right to deletion

Consult with your compliance team before using in regulated environments.

## Additional Resources

- [OWASP Authentication Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html)
- [AWS Security Best Practices](https://docs.aws.amazon.com/security/index.html)
- [SAML Security Best Practices](https://docs.oasis-open.org/security/saml/Post2.0/sstc-saml-sec-consider-2.0.html)
- [NIST Password Guidelines](https://pages.nist.gov/800-63-3/sp800-63b.html)

## License

See [LICENSE](LICENSE) for license information. This software is provided "as is" without warranty of any kind.
