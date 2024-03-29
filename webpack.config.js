const path = require('path');
const HtmlWebpackPlugin = require('html-webpack-plugin');

const build_dir = path.resolve(__dirname, 'htdocs');
const src_dir = path.resolve(__dirname, 'src');


const htmlLoaderAttributes = {
    list: [
        {
            tag: 'meta',
            attribute: 'content',
            type: 'src',
            filter: (tag, attribute,
                     attributes) => {
                if (/(og|twitter):image$/.test(attributes.property)) {
                    return true;
                }

                return false;
            },
        },
        {
            tag: 'img',
            attribute: 'src',
            type: 'src',
        },
        {
            tag: 'img',
            attribute: 'srcset',
            type: 'srcset',
        },
        {
            tag: 'link',
            attribute: 'href',
            type: 'src',
        },
        {
            tag: 'script',
            attribute: 'src',
            type: 'src',
        },
    ],
};


module.exports = (_, env) => ({
    context: src_dir,
    devServer: {
        contentBase: build_dir,
        compress: true,
        port: 8090,
    },
    entry: {
        main: [
            path.resolve(src_dir, 'js', 'common.js'),
            path.resolve(src_dir, 'js', 'dashboard.js'),
        ],
        schools: [
            path.resolve(src_dir, 'js', 'common.js'),
            path.resolve(src_dir, 'js', 'schools.js'),
        ],
    },
    module: {
        rules: [
            {
                test: /\.js$/,
                exclude: /node_modules/,
                loader: 'babel-loader',
                options: {
                    presets: ['@babel/preset-env'],
                },
            },
            {
                test: /\.less$/,
                exclude: /node_modules/,
                use: [
                    {
                        loader: 'file-loader',
                        options: {
                            name: '[path][name].[contenthash:8].css',
                        },
                    },
                    'extract-loader',
                    'css-loader',
                    'less-loader',
                ],
            },
            {
                test: /\.(png|svg)$/,
                exclude: /node_modules/,
                use: [
                    {
                        loader: 'file-loader',
                        options: {
                            name: (resourcePath, resourceQuery) => {
                                if (/favicon.png$/.test(resourcePath)) {
                                    return '[name].[ext]';
                                } else {
                                    return '[path][name].[contenthash:8].[ext]';
                                }
                            },
                        },
                    },
                ],
            },
            {
                test: /\.html$/,
                exclude: /node_modules/,
                use: [
                    {
                        loader: 'html-loader',
                        options: {
                            minimize: false,
                            attributes: htmlLoaderAttributes,
                        },
                    },
                ],
            },
        ],
    },
    output: {
        path: path.resolve(build_dir),
        filename: 'js/[name].[contenthash:8].js',
        publicPath: (env.mode === 'production' ? 'https://bc19.live/' : '/'),
    },
    plugins: [
        new HtmlWebpackPlugin({
            filename: './index.html',
            template: 'index.html',
            chunks: ['main'],
        }),
        new HtmlWebpackPlugin({
            filename: './schools.html',
            template: 'schools.html',
            chunks: ['schools'],
        }),
    ],
});
