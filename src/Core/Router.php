<?php

namespace Cauri\Core;

/** Routeur minimal : motifs "/classements/{country}/{chart}" et contraintes regex facultatives. */
final class Router
{
    private array $routes = [];

    public function get(string $pattern, callable|array $handler): void
    {
        $this->add('GET', $pattern, $handler);
    }

    public function post(string $pattern, callable|array $handler): void
    {
        $this->add('POST', $pattern, $handler);
    }

    public function add(string $method, string $pattern, callable|array $handler): void
    {
        $regex = preg_replace_callback(
            '#\{(\w+)(?::((?:[^{}]|\{[^{}]*\})+))?\}#', // la contrainte peut contenir {2}
            fn ($m) => '(?P<' . $m[1] . '>' . ($m[2] ?? '[^/]+') . ')',
            $pattern
        );
        $this->routes[] = [$method, '#^' . $regex . '$#u', $handler];
    }

    public function dispatch(Request $request): Response
    {
        $allowed = false;
        foreach ($this->routes as [$method, $regex, $handler]) {
            if (!preg_match($regex, $request->path, $m)) {
                continue;
            }
            if ($method !== $request->method) {
                $allowed = true;
                continue;
            }
            $request->params = array_filter($m, 'is_string', ARRAY_FILTER_USE_KEY);
            if (is_array($handler)) {
                [$class, $action] = $handler;
                return (new $class())->$action($request);
            }
            return $handler($request);
        }
        throw new HttpException($allowed ? 405 : 404);
    }
}
