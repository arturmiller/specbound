import { defineConfig } from 'vite';
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';

function bundledLicenses() {
  return {
    name: 'specbound-bundled-licenses',
    apply: 'build',
    generateBundle: {
      order: 'post',
      handler(_options, bundle) {
        const chunks = {};
        const packages = new Map();
        for (const chunk of Object.values(bundle)) {
          if (chunk.type !== 'chunk') continue;
          chunks[chunk.fileName] = createHash('sha256').update(chunk.code).digest('hex');
          for (const [id, module] of Object.entries(chunk.modules)) {
            if (!module.renderedLength) continue;
            const path = id.replace(/\\/g, '/').replace(/^\0/, '');
            const marker = '/node_modules/';
            const start = path.lastIndexOf(marker);
            if (start < 0) continue;
            const segments = path.slice(start + marker.length).split('/');
            const name = segments.slice(0, segments[0].startsWith('@') ? 2 : 1).join('/');
            const manifest = path.slice(0, start + marker.length) + name + '/package.json';
            if (packages.has(manifest)) continue;
            const { version, license } = JSON.parse(readFileSync(manifest, 'utf8'));
            packages.set(manifest, { name, version, license: typeof license === 'string' ? license : null });
          }
        }
        const dependencies = [...packages.values()].sort((left, right) => left.name.localeCompare(right.name) || left.version.localeCompare(right.version));
        this.emitFile({ type: 'asset', fileName: 'bundled-licenses.json', source: JSON.stringify({ chunks, dependencies }, null, 2) + '\n' });
      },
    },
  };
}

export default defineConfig({
  plugins: [bundledLicenses()],
  server: {
    proxy: {
      '/api': {
        target: process.env.API_PROXY_TARGET || 'http://localhost:8000',
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
});
