
module.exports = {
  apps: [
    {
      name: 'simex',
      script: 'server.js',
      cwd: __dirname,            // garante que o PM2 rode a partir da pasta do projeto
      exec_mode: 'fork',         // "cluster" se quiser múltiplos workers
      instances: 1,
      watch: false,              // true em dev, se quiser reiniciar ao salvar arquivos
      ignore_watch: ['node_modules', 'logs', '.git'],
      max_memory_restart: '300M',
      restart_delay: 2000,
      time: true,                // prefixa data/hora nos logs
      out_file: './logs/simex-out.log',
      error_file: './logs/simex-error.log',
      env: {
        NODE_ENV: 'development',
        PORT: 3002
      },
      env_production: {
        NODE_ENV: 'production',
        PORT: process.env.PORT || 8052
      }
    }
  ]
};
