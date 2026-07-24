-- CreateTable
CREATE TABLE "products" (
    "id" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "description" TEXT,
    "category" TEXT,
    "subCategory" TEXT,
    "articleType" TEXT,
    "gender" TEXT,
    "color" TEXT,
    "season" TEXT,
    "usage" TEXT,
    "image" TEXT,
    "price" DOUBLE PRECISION NOT NULL DEFAULT 0,
    "embedding" JSONB,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "products_pkey" PRIMARY KEY ("id")
);
