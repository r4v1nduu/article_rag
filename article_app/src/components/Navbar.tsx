"use client";

import React from "react";
import { Button } from "@/components/ui/button";
import { ThemeToggle } from "@/components/theme-toggle";
import Link from "next/link";
import { CogIcon } from "@heroicons/react/24/outline";

interface NavbarProps {
  currentPage?: "home" | "add" | "manage";
}

const navigation = [
  {
    name: "Admin Dashboard",
    href: "/manage",
    current: false,
    page: "manage",
    icon: CogIcon,
  },
];

function classNames(...classes: string[]) {
  return classes.filter(Boolean).join(" ");
}

export default function Navbar({ currentPage = "home" }: NavbarProps) {
  // Update navigation to mark current page
  const updatedNavigation = navigation.map((item) => ({
    ...item,
    current: item.page === currentPage,
  }));

  return (
    <nav className="bg-background border-b border-border">
      <div className="mx-auto max-w-7xl px-2 sm:px-6 lg:px-8">
        <div className="relative flex h-16 items-center justify-between">
          <div className="flex flex-1 items-center justify-center sm:items-stretch sm:justify-start">
            <div className="flex shrink-0 items-center">
              <Link href="/" className="text-2xl font-bold text-foreground">
                EMS
              </Link>
            </div>
            <div className="hidden sm:ml-6 sm:block lg:px-6">
              <div className="flex space-x-4">
                {updatedNavigation.map((item) => (
                  <Link key={item.name} href={item.href}>
                    <Button variant="outline" size="sm">
                      <div className="flex items-center space-x-2">
                        <item.icon className="h-5 w-5" aria-hidden="true" />
                        <span>{item.name}</span>
                      </div>
                    </Button>
                  </Link>
                ))}
              </div>
            </div>
          </div>

          <div className="absolute inset-y-0 right-0 flex items-center pr-2 sm:static sm:inset-auto sm:ml-6 sm:pr-0">
            {/* Theme Toggle */}
            <div className="mr-3">
              <ThemeToggle />
            </div>

            {/* Profile placeholder */}
            <div className="relative ml-3">
              <div className="relative flex rounded-full focus:outline-none">
                <span className="absolute -inset-1.5" />
                <span className="sr-only">User profile</span>
                <div className="h-8 w-8 rounded-full bg-muted flex items-center justify-center border border-border">
                  <span className="text-xs font-medium text-muted-foreground">
                    RD
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </nav>
  );
}
