# vitest 5 requires Node ^22.12.0 || ^24 || >=26, and vite 8 requires
# ^20.19.0 || >=22.12.0, so node:20-alpine can no longer build this.
# Keep in sync with NODE_VERSION in .github/workflows/ci.yml.
FROM node:22-alpine AS builder
WORKDIR /app
# Copy the lockfile and install from it. Copying only package.json made every
# build re-resolve the whole tree from the registry, so builds were not
# reproducible and ignored the lockfile entirely.
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
