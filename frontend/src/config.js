const config = {
  // Development
  development: {
    apiBaseUrl: 'http://localhost:8000',
    imageBaseUrl: 'http://localhost:8000/images'
  },
  // Production
  production: {
    apiBaseUrl: 'https://pax-tt-app.fly.dev',
    imageBaseUrl: 'https://your-cloudflare-r2-domain.com' // Your Cloudflare R2 domain
  }
};

const environment = process.env.NODE_ENV || 'development';
export const apiBaseUrl = config[environment].apiBaseUrl;
export const imageBaseUrl = config[environment].imageBaseUrl; 