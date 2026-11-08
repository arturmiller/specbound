// Development-only OIDC provider. Never expose this service outside localhost.
import { Provider, errors } from 'oidc-provider';

const issuer = 'http://127.0.0.1:15556';
const audience = 'urn:specbound:api';
const configuration = {
  clients: [{
    client_id: 'specbound-web',
    redirect_uris: ['http://127.0.0.1:5173/'],
    token_endpoint_auth_method: 'none',
    response_types: ['code'],
    grant_types: ['authorization_code'],
  }],
  features: {
    devInteractions: { enabled: true },
    resourceIndicators: {
      enabled: true,
      // The browser requests the resource during authorization; its token
      // request omits it. Accept only the previously granted resource.
      async useGrantedResource() { return true; },
      async getResourceServerInfo(_ctx, resource) {
        if (resource !== audience) throw new errors.InvalidTarget();
        return { scope: 'openid profile', audience, accessTokenFormat: 'jwt', accessTokenTTL: 3600 };
      },
    },
  },
};

const provider = new Provider(issuer, configuration);
provider.listen(5556, '0.0.0.0');
