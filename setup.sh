#!/bin/bash

echo "🚀 GarsonAI Setup Script"
echo "========================"

# Check if .env exists
if [ ! -f "backend/.env" ]; then
    echo "⚠️  Creating .env file from example..."
    cp backend/.env.example backend/.env
    echo "✅ Please edit backend/.env with your API keys!"
    echo "   - DATABASE_URL"
    echo "   - SECRET_KEY"
    echo "   - FAL_KEY"
    echo "   - OPENROUTER_API_KEY"
    echo ""
    read -p "Press enter after configuring .env..."
fi

echo "📦 Installing backend dependencies..."
cd backend
pip install -r requirements.txt
cd ..

echo "📦 Installing frontend dependencies..."
cd frontend
npm install
cd ..

echo ""
echo "✅ Setup complete!"
echo ""
echo "🎯 Next steps:"
echo "1. Make sure PostgreSQL is running"
echo "2. Backend: cd backend && uvicorn main:app --reload"
echo "3. Frontend: cd frontend && npm run dev"
echo ""
echo "🌐 URLs:"
echo "   Backend: http://localhost:8000"
echo "   Frontend: http://localhost:5173"
echo ""
