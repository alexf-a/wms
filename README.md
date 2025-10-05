# wms
A web-native app for organizing and finding your sh*t!

Personal storage comes with two major pain points:
1) Storage unit transparency: We are unsure what items exist in individual units of storage (such as bins, lockers, sheds, etc.)
2) Individual item location: We are unsure of the whereabouts of particular items. 

WMS seeks to address both pain-points:
1) Storage unit transparency is increased through a simple digital inventory system
2) Items are located through advanced search capabilities, using image and natural language inputs for user convenience.

## 🚀 Deployment

This project deploys to AWS Lightsail Container Service with PostgreSQL database support.

### Prerequisites

- Docker Desktop installed and running
- AWS CLI configured with appropriate permissions
- Poetry for dependency management
- A PostgreSQL database (we recommend [Neon](https://neon.tech) for cloud PostgreSQL)

### First-Time Deployment

1. **Setup your database**: Get your PostgreSQL connection string
   ```
   postgresql://username:password@host:port/database?sslmode=require
   ```

2. **Create your configuration**:
   ```bash
   cp lightsail/containers.example.json lightsail/containers.json
   ```
   Update `lightsail/containers.json` with your database credentials and generate a secure `SECRET_KEY`.

3. **Initial setup**:
   ```bash
   make setup
   ```
   This will:
   - Install patched lightsailctl (fixes AWS bugs)
   - Build your Docker image 
   - Create the Lightsail container service
   - Display the service URL

4. **Configure allowed hosts**:
   Update the `ALLOWED_HOSTS` in `lightsail/containers.json` with the URL from step 3.

5. **Complete deployment**:
   ```bash
   make setup-deploy
   ```

Your app will be live at the Lightsail URL! 🎉

### Regular Deployments

For subsequent deployments after code changes:

```bash
make up
```

This builds, pushes, and deploys your latest changes.

### Available Commands

- `make help` - Show all available commands
- `make docker-build` - Build Docker image
- `make create` - Create Lightsail service
- `make push` - Push image to Lightsail
- `make deploy` - Deploy to Lightsail
- `make down` - Delete service (stops billing)

### Troubleshooting

**"image push response does not contain the image digest" error**:
```bash
make install-lightsailctl-fix
```

**Docker platform issues**: The Makefile automatically uses `linux/amd64` platform for Lightsail compatibility.

### Tech Stack

- **Backend**: Django + PostgreSQL
- **Deployment**: AWS Lightsail Container Service
- **Container**: Docker with Gunicorn
- **Dependencies**: Poetry
- **Search**: LLM-powered search capabilities 