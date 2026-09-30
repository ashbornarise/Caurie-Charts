<?php

namespace Cauri\Core;

final class HttpException extends \RuntimeException
{
    public function __construct(public readonly int $status, string $message = '')
    {
        parent::__construct($message, $status);
    }
}
