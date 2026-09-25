FROM node:24-bookworm-slim
ENV NEXT_TELEMETRY_DISABLED=1
WORKDIR /app/frontend
COPY package.json package-lock.json ./
RUN npm ci && mkdir -p .next && chown -R node:node /app/frontend
COPY --chown=node:node . .
USER node
EXPOSE 3000
CMD ["npm", "run", "dev", "--", "--hostname", "0.0.0.0"]
