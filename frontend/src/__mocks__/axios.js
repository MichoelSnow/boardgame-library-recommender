const joinUrl = (baseURL = '', path = '') => {
  const normalizedBase = String(baseURL || '').replace(/\/+$/, '');
  const normalizedPath = String(path || '').replace(/^\/+/, '');
  if (!normalizedBase) {
    return `/${normalizedPath}`;
  }
  return `${normalizedBase}/${normalizedPath}`;
};

const buildUrlWithParams = (url, params) => {
  if (!params || typeof params !== 'object') {
    return url;
  }
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null) {
      return;
    }
    search.append(key, String(value));
  });
  const query = search.toString();
  return query ? `${url}?${query}` : url;
};

const parseBody = async (response) => {
  const text = await response.text();
  if (!text) {
    return null;
  }
  try {
    return JSON.parse(text);
  } catch (_) {
    return text;
  }
};

const buildHeaders = (defaults, requestHeaders = {}) => ({
  ...(defaults?.common || {}),
  ...(requestHeaders || {}),
});

const hasHeader = (headers, key) =>
  Object.keys(headers).some((name) => name.toLowerCase() === key.toLowerCase());

const normalizeRequestBody = (data, headers) => {
  if (data === undefined || data === null) {
    return undefined;
  }

  if (typeof URLSearchParams !== 'undefined' && data instanceof URLSearchParams) {
    if (!hasHeader(headers, 'content-type')) {
      headers['Content-Type'] = 'application/x-www-form-urlencoded';
    }
    return data.toString();
  }

  if (typeof data === 'object') {
    if (!hasHeader(headers, 'content-type')) {
      headers['Content-Type'] = 'application/json';
    }
    return JSON.stringify(data);
  }

  return data;
};

const create = ({ baseURL } = {}) => {
  const defaults = { headers: { common: {} } };

  const request = async (method, path, data, config = {}) => {
    const urlWithPath = joinUrl(baseURL, path);
    const url = buildUrlWithParams(urlWithPath, config.params);
    const headers = buildHeaders(defaults.headers, config.headers);

    const body = normalizeRequestBody(data, headers);

    const response = await fetch(url, {
      method,
      headers,
      body,
    });
    const parsed = await parseBody(response);
    const axiosLike = {
      data: parsed,
      status: response.status,
      headers: Object.fromEntries(response.headers.entries()),
    };
    if (!response.ok) {
      const error = new Error(`Request failed with status ${response.status}`);
      error.response = axiosLike;
      throw error;
    }
    return axiosLike;
  };

  return {
    defaults,
    get: (path, config) => request('GET', path, undefined, config),
    post: (path, data, config) => request('POST', path, data, config),
    put: (path, data, config) => request('PUT', path, data, config),
  };
};

const axios = { create };

export default axios;
