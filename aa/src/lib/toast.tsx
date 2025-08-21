"use client";

import { toast as sonnerToast } from "sonner";
import { CheckCircleIcon, XCircleIcon, ExclamationTriangleIcon } from "@heroicons/react/24/outline";

export const toast = {
  success: (message: string, description?: string) => {
    sonnerToast.success(message, {
      description,
      icon: <CheckCircleIcon className="h-5 w-5 text-green-500" />,
    });
  },
  error: (message: string, description?: string) => {
    sonnerToast.error(message, {
      description,
      icon: <XCircleIcon className="h-5 w-5 text-red-500" />,
    });
  },
  warning: (message: string, description?: string) => {
    sonnerToast.warning(message, {
      description,
      icon: <ExclamationTriangleIcon className="h-5 w-5 text-yellow-500" />,
    });
  },
};
