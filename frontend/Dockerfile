FROM node:22-alpine AS dependencies
WORKDIR /workspace/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

FROM dependencies AS development
COPY frontend ./
EXPOSE 5173
CMD ["npm", "run", "dev"]

FROM dependencies AS build
ARG VITE_API_BASE_URL=/
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
COPY frontend ./
RUN npm run build

FROM nginx:1.27-alpine AS production
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /workspace/frontend/dist /usr/share/nginx/html
EXPOSE 80
HEALTHCHECK --interval=10s --timeout=3s --retries=5 CMD wget -q -O - http://localhost/healthz || exit 1
