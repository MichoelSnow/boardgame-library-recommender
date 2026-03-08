const config = {
  // Development
  development: {
    apiBaseUrl: 'http://localhost:8000/api',
    imageBaseUrl: 'http://localhost:8000/images'
  },
  // Production
  production: {
    apiBaseUrl: '/api',
    // Use direct BoardGameGeek images until Cloudflare is set up
    imageBaseUrl: null // Setting to null indicates we should use direct BGG URLs
  }
};

const environment = process.env.NODE_ENV || 'development';
const resolvedEnvironment = config[environment] ? environment : 'development';

export const apiBaseUrl = config[resolvedEnvironment].apiBaseUrl;
export const imageBaseUrl = config[resolvedEnvironment].imageBaseUrl;
