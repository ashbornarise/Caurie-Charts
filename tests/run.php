<?php

/**
 * Lanceur de tests autonome (aucune dépendance) : php tests/run.php [filtre]
 * Chaque fichier tests/*Test.php retourne un tableau ['nom du test' => callable].
 */

require dirname(__DIR__) . '/src/bootstrap.php';
require __DIR__ . '/support.php';

final class AssertionFailed extends Exception
{
}

function assert_same(mixed $expected, mixed $actual, string $message = ''): void
{
    if ($expected !== $actual) {
        throw new AssertionFailed(($message ? "$message\n" : '') . '  attendu : ' . var_export($expected, true) . "\n  obtenu  : " . var_export($actual, true));
    }
}

function assert_true(bool $condition, string $message = 'condition fausse'): void
{
    if (!$condition) {
        throw new AssertionFailed($message);
    }
}

function assert_contains(mixed $needle, array $haystack, string $message = ''): void
{
    if (!in_array($needle, $haystack, true)) {
        throw new AssertionFailed(($message ? "$message\n" : '') . '  ' . var_export($needle, true) . ' absent de ' . json_encode($haystack));
    }
}

function assert_not_contains(mixed $needle, array $haystack, string $message = ''): void
{
    if (in_array($needle, $haystack, true)) {
        throw new AssertionFailed(($message ? "$message\n" : '') . '  ' . var_export($needle, true) . ' présent dans ' . json_encode($haystack));
    }
}

$filter = $argv[1] ?? '';
$passed = 0;
$failed = [];

foreach (glob(__DIR__ . '/*Test.php') as $file) {
    $suite = basename($file, '.php');
    foreach (require $file as $name => $test) {
        if ($filter !== '' && stripos("$suite $name", $filter) === false) {
            continue;
        }
        try {
            $test();
            $passed++;
            echo "  \u{2713} $suite : $name\n";
        } catch (Throwable $e) {
            $failed[] = "$suite : $name";
            echo "  \u{2717} $suite : $name\n" . $e->getMessage() . "\n";
            if (!$e instanceof AssertionFailed) {
                echo '  ' . get_class($e) . ' ' . $e->getFile() . ':' . $e->getLine() . "\n";
            }
        }
    }
}

echo "\n$passed réussi(s), " . count($failed) . " échec(s)\n";
exit($failed ? 1 : 0);
